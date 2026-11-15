"""Atomic, revision-aware persistence for the file-based Cameco adapter."""
from datetime import date, datetime
from hashlib import sha256
import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from app.db.schema import metrics, observations, runs, sources
from app.ingestion.cameco_prices import MAX_BYTES, METHOD_VERSION, SOURCE_URL, parse_prices

logger = logging.getLogger(__name__)
LOCK_ID = 714202605  # Serialize this small monthly importer across concurrent processes.


def _get_or_create(connection, table, values, key):
    connection.execute(insert(table).values(**values).on_conflict_do_nothing(index_elements=[table.c[key]]))
    row = connection.execute(sa.select(table).where(table.c[key] == values[key])).mappings().one()
    if any(row[name] != value for name, value in values.items()):
        raise ValueError(f"Stored {table.name} definition conflicts with importer; use a new series/method")
    return row["id"]


def _save_artifact(raw_dir: Path, checksum: str, body: bytes) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact = raw_dir / f"{checksum}.html"
    try:
        with artifact.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if artifact.read_bytes() != body:
            raise ValueError("Existing artifact bytes do not match checksum") from None
    return artifact.resolve()


def import_prices(engine, body: bytes, *, retrieved_at: datetime, raw_dir: Path,
                  synthetic: bool = False, permission_reference: str | None = None,
                  publication_date: date | None = None) -> dict:
    if not synthetic and not (permission_reference and permission_reference.strip()):
        raise ValueError("Actual source permission is required; see data/README.md")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must include timezone")
    if len(body) > MAX_BYTES:
        raise ValueError("HTML file exceeds 5 MB limit")
    checksum = sha256(body).hexdigest()
    artifact = _save_artifact(raw_dir, checksum, body)
    source_name = "Workshop synthetic Cameco-shaped fixture" if synthetic else "Cameco"
    source_url = "https://example.invalid/cameco-shaped-fixture" if synthetic else SOURCE_URL
    source_notes = "Synthetic parser exercise; no Cameco observations" if synthetic else "Cameco public price indicators; underlying UxC/TradeTech inputs; permission required"
    with engine.begin() as connection:
        source_id = _get_or_create(connection, sources, dict(
            name=source_name, url=source_url, cadence="monthly", notes=source_notes,
        ), "name")
        run_id = connection.execute(runs.insert().values(
            source_id=source_id, source_url=source_url, source_table="historical price HTML table",
            source_vintage=f"sha256:{checksum}", source_publication_date=publication_date,
            retrieved_at=retrieved_at, artifact_sha256=checksum, artifact_path=str(artifact),
            method_version=METHOD_VERSION, status="running",
            notes="Synthetic local file" if synthetic else f"Permission reference: {permission_reference}",
        ).returning(runs.c.id)).scalar_one()
    try:
        parsed = parse_prices(body.decode("utf-8"))
        with engine.begin() as connection:
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
            metric_ids = {}
            for series, label in [("uranium_spot", "Spot price indicator"), ("uranium_long_term", "Long-term price indicator")]:
                series_id = f"workshop_cameco_{series}" if synthetic else f"cameco_{series}"
                metric_ids[series] = _get_or_create(connection, metrics, dict(
                    source_id=source_id, series_id=series_id, label=f"{label} — mock" if synthetic else label,
                    unit="USD/lb U3O8", currency="USD", geography="Global",
                    covered_population="Synthetic teaching values" if synthetic else "Published market indicators; not a surveyed transaction population",
                    measure_type="price_indicator",
                    methodology_notes="Monthly indicator; first-of-month storage is a period label. Long-term before May 2004: TradeTech only; otherwise Cameco average of month-end UxC/TradeTech inputs. Unit cross-checked against Cameco annual reporting; not labelled in current HTML table.",
                ), "series_id")
            incoming = {(metric_ids[point.series_id], point.observation_date) for point in parsed.observations}
            existing = set(connection.execute(sa.select(
                observations.c.metric_id, observations.c.observation_date,
            ).where(observations.c.metric_id.in_(list(metric_ids.values())))))
            added = revised = unchanged = 0
            previous_artifact = connection.execute(sa.select(runs.c.id).where(
                runs.c.source_id == source_id, runs.c.artifact_sha256 == checksum,
                runs.c.method_version == METHOD_VERSION, runs.c.status == "succeeded",
            )).first()
            if previous_artifact:
                unchanged = len(parsed.observations)
            else:
                if existing - incoming:
                    raise ValueError("Historical months disappeared from the source; import aborted for review")
                for point in parsed.observations:
                    metric_id = metric_ids[point.series_id]
                    prior = connection.execute(sa.select(observations).where(
                        observations.c.metric_id == metric_id,
                        observations.c.observation_date == point.observation_date,
                    ).order_by(observations.c.id.desc()).limit(1)).mappings().first()
                    status = "available" if point.value is not None else "missing"
                    if prior and prior["normalized_value"] == point.value and prior["value_status"] == status:
                        unchanged += 1
                        continue
                    # Do not turn an older saved snapshot into a revision of a newer one.
                    if prior:
                        prior_time = connection.scalar(sa.select(runs.c.retrieved_at).where(runs.c.id == prior["ingestion_run_id"]))
                        if retrieved_at <= prior_time:
                            raise ValueError("Changed historical snapshot is not newer than the current value; import aborted")
                    result = connection.execute(insert(observations).values(
                        metric_id=metric_id, source_id=source_id, ingestion_run_id=run_id,
                        artifact_sha256=checksum, observation_date=point.observation_date,
                        raw_value=point.raw_value, normalized_value=point.value, value_status=status,
                        data_status="mock" if synthetic else ("revised" if prior else "observed"),
                        supersedes_observation_id=prior["id"] if prior else None,
                        quality_notes=point.methodology_notes + (" Synthetic values." if synthetic else "") +
                                      (" Revision of earlier value." if prior else ""),
                    ).on_conflict_do_nothing(constraint="uq_observation_artifact_period").returning(observations.c.id))
                    if result.scalar_one_or_none() is None:
                        unchanged += 1
                    elif prior:
                        revised += 1
                    else:
                        added += 1
            notes = {"added": added, "revised": revised, "unchanged": unchanged,
                     "warnings": list(parsed.warnings), "publication_date_known": publication_date is not None}
            connection.execute(runs.update().where(runs.c.id == run_id).values(
                status="succeeded", notes=("Synthetic local file. " if synthetic else f"Permission reference: {permission_reference}. ") + str(notes),
            ))
        logger.info("Cameco import succeeded run_id=%s added=%s revised=%s unchanged=%s", run_id, added, revised, unchanged)
        return {"run_id": run_id, "checksum": checksum, **notes}
    except Exception as error:
        # Observation writes roll back together; a separate transaction retains failure metadata.
        with engine.begin() as connection:
            connection.execute(runs.update().where(runs.c.id == run_id).values(
                status="failed", notes=("Synthetic local file. " if synthetic else f"Permission reference: {permission_reference}. ") + f"{type(error).__name__}: source parsing/import failed; see command error",
            ))
        logger.error("Cameco import failed run_id=%s error_type=%s", run_id, type(error).__name__)
        raise
