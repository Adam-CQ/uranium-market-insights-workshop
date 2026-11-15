"""Retain EIA workbooks and import each table/year atomically with revisions."""
from datetime import date, datetime
from hashlib import sha256
import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from app.db.schema import metrics, observations, runs, sources
from app.ingestion.eia_contracting import BASE_URL, FILES, MAX_BYTES, METHOD_VERSION, POPULATION, PRICE_UNIT, SOURCE_NAME, parse_workbook

logger = logging.getLogger(__name__)


def _definition(connection, table, values, key):
    connection.execute(insert(table).values(**values).on_conflict_do_nothing(index_elements=[table.c[key]]))
    row = connection.execute(sa.select(table).where(table.c[key] == values[key])).mappings().one()
    if any(row[k] != v for k, v in values.items()):
        raise ValueError(f"Existing {table.name} definition differs; review series versioning")
    return row["id"]


def import_contracts(engine, body: bytes, *, table: int, report_year: int,
                     retrieved_at: datetime, publication_date: date, raw_dir: Path) -> dict:
    if table not in FILES or not 1900 <= report_year <= 9998:
        raise ValueError("Unsupported table or report year")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must include timezone")
    if publication_date > retrieved_at.date():
        raise ValueError("Publication date cannot follow retrieval date")
    if len(body) > MAX_BYTES:
        raise ValueError("Workbook exceeds 5 MB")
    checksum = sha256(body).hexdigest()
    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact = raw_dir / f"{checksum}.xlsx"
    try:
        with artifact.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if artifact.read_bytes() != body:
            raise ValueError("Existing artifact differs from expected checksum") from None
    source_table = f"EIA Table {table}"
    url = BASE_URL + "xls/" + FILES[table]
    with engine.begin() as connection:
        source_id = _definition(connection, sources, dict(
            name=SOURCE_NAME, url=BASE_URL + "index.php", cadence="annual",
            notes="UMAR, Form EIA-858. U.S. civilian reactor owners/operators only; EIA public-domain data with attribution.",
        ), "name")
        run_id = connection.execute(runs.insert().values(
            source_id=source_id, source_url=url, source_table=source_table,
            source_vintage=f"UMAR {report_year}; report publication/revision {publication_date}; sha256:{checksum}",
            source_publication_date=publication_date, retrieved_at=retrieved_at,
            artifact_sha256=checksum, artifact_path=str(artifact.resolve()),
            method_version=METHOD_VERSION, status="running", notes="Local workbook; source metadata supplied explicitly",
        ).returning(runs.c.id)).scalar_one()
    try:
        parsed = parse_workbook(body, table=table, report_year=report_year)
        with engine.begin() as connection:
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": 714202606})
            metric_ids = {}
            for spec in {fact.metric for fact in parsed.facts}:
                metric_ids[spec.series_id] = _definition(connection, metrics, dict(
                    source_id=source_id, series_id=spec.series_id, label=spec.label,
                    unit=spec.unit, currency="USD" if spec.unit == PRICE_UNIT else None,
                    geography="United States", covered_population=POPULATION,
                    measure_type=spec.measure_type,
                    methodology_notes=(
                        f"EIA Table {table}; material={spec.material_type}; supplier={spec.supplier_scope}; bound={spec.quantity_bound}. "
                        "Preserve source units and U3O8-equivalent basis; no inflation adjustment. "
                        "Spot: usually one delivery within a year of signing; long-term: one or more deliveries at least a year after signing. "
                        "Totals and components are separate, overlapping records; never sum them together."
                    ),
                ), "series_id")
            previous = connection.execute(sa.select(runs.c.id).where(
                runs.c.source_id == source_id, runs.c.source_table == source_table,
                runs.c.artifact_sha256 == checksum, runs.c.status == "succeeded",
                runs.c.method_version == METHOD_VERSION,
            )).first()
            added = revised = unchanged = 0
            if previous:
                unchanged = len(parsed.facts)
            else:
                for fact in parsed.facts:
                    metric_id = metric_ids[fact.metric.series_id]
                    prior = connection.execute(sa.select(observations).where(
                        observations.c.metric_id == metric_id,
                        observations.c.report_year == report_year,
                        observations.c.delivery_year == fact.delivery_year,
                        observations.c.contract_type == fact.contract_type,
                    ).order_by(observations.c.id.desc()).limit(1)).mappings().first()
                    if prior and prior["normalized_value"] == fact.value and prior["value_status"] == fact.value_status:
                        unchanged += 1
                        continue
                    if prior:
                        prior_time = connection.scalar(sa.select(runs.c.retrieved_at).where(runs.c.id == prior["ingestion_run_id"]))
                        if retrieved_at <= prior_time:
                            raise ValueError("Changed snapshot is not newer than existing value; import aborted")
                    connection.execute(observations.insert().values(
                        metric_id=metric_id, source_id=source_id, ingestion_run_id=run_id,
                        artifact_sha256=checksum, report_year=report_year, delivery_year=fact.delivery_year,
                        contract_type=fact.contract_type, raw_value=fact.raw_value,
                        normalized_value=fact.value, value_status=fact.value_status,
                        data_status="revised" if prior else "observed",
                        supersedes_observation_id=prior["id"] if prior else None,
                        quality_notes=(
                            f"{parsed.title}. Cell {fact.cell}; {parsed.release_label}. "
                            "Numeric cells normalized to 8 decimal places; original workbook retained. "
                            "W means withheld, not zero. Null delivery_year in Tables 9/10 is the published horizon total. "
                            + " ".join(parsed.warnings)
                        ),
                    ))
                    if prior:
                        revised += 1
                    else:
                        added += 1
            result = {"table": table, "report_year": report_year, "run_id": run_id,
                      "checksum": checksum, "added": added, "revised": revised,
                      "unchanged": unchanged, "warnings": list(parsed.warnings)}
            connection.execute(runs.update().where(runs.c.id == run_id).values(status="succeeded", notes=str(result)))
        logger.info("EIA import succeeded run_id=%s table=%s added=%s revised=%s", run_id, table, added, revised)
        return result
    except Exception as error:
        with engine.begin() as connection:
            connection.execute(runs.update().where(runs.c.id == run_id).values(
                status="failed", notes=f"{type(error).__name__}: workbook parsing/import failed; see command error",
            ))
        logger.error("EIA import failed run_id=%s table=%s error_type=%s", run_id, table, type(error).__name__)
        raise
