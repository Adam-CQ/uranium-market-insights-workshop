"""Executable synthetic provenance example; all writes are rolled back."""
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from app.db.connection import database_engine
from app.db.schema import metrics, observations, runs, sources


def insert_fixture(connection) -> int:
    source_id = connection.execute(insert(sources).values(
        name="Workshop synthetic source", url="https://example.invalid/workshop",
        cadence="monthly example", notes="Synthetic; not Cameco observations",
    ).on_conflict_do_update(index_elements=[sources.c.name], set_={"notes": "Synthetic; not Cameco observations"}).returning(sources.c.id)).scalar_one()
    metric_id = connection.execute(insert(metrics).values(
        source_id=source_id, series_id="workshop_mock_spot", label="Mock spot indicator",
        unit="USD/lb U3O8", currency="USD", geography="Global (illustrative only)",
        covered_population="No surveyed population", measure_type="price_indicator",
        methodology_notes="Invented fixture; observation_date is a month-end date",
    ).on_conflict_do_nothing(index_elements=[metrics.c.series_id]).returning(metrics.c.id)).scalar_one_or_none()
    if metric_id is None:
        metric_id = connection.execute(sa.select(metrics.c.id).where(metrics.c.series_id == "workshop_mock_spot")).scalar_one()
    checksum = sha256(b"synthetic fixture June 2025: 76.00").hexdigest()
    run_id = connection.execute(runs.insert().values(
        source_id=source_id, source_url="https://example.invalid/workshop",
        source_table="mock prices", source_vintage="workshop-mock-v1",
        retrieved_at=datetime.now(timezone.utc), artifact_sha256=checksum,
        artifact_path="generated:workshop-example", method_version="demo-v1",
        status="succeeded", notes="Generated locally, not retrieved from a publisher",
    ).returning(runs.c.id)).scalar_one()
    values = dict(metric_id=metric_id, source_id=source_id, ingestion_run_id=run_id,
                  artifact_sha256=checksum, observation_date=date(2025, 6, 30),
                  raw_value="76.00", normalized_value=Decimal("76.00"),
                  value_status="available", data_status="mock", quality_notes="Invented teaching value")
    observation_id = connection.execute(insert(observations).values(**values).on_conflict_do_nothing(
        constraint="uq_observation_artifact_period"
    ).returning(observations.c.id)).scalar_one_or_none()
    if observation_id is None:
        observation_id = connection.execute(sa.select(observations.c.id).where(
            observations.c.metric_id == metric_id, observations.c.artifact_sha256 == checksum,
            observations.c.observation_date == date(2025, 6, 30),
        )).scalar_one()
    return observation_id


def main():
    engine = database_engine()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                observation_id = insert_fixture(connection)
                assert insert_fixture(connection) == observation_id
                row = connection.execute(sa.select(
                    sources.c.name, metrics.c.series_id, metrics.c.unit,
                    observations.c.observation_date, observations.c.raw_value,
                    observations.c.normalized_value, observations.c.data_status,
                    runs.c.source_vintage, runs.c.artifact_sha256,
                ).select_from(observations.join(metrics, observations.c.metric_id == metrics.c.id)
                              .join(sources, metrics.c.source_id == sources.c.id)
                              .join(runs, observations.c.ingestion_run_id == runs.c.id))
                  .where(observations.c.id == observation_id)).mappings().one()
                print(dict(row))
                print("Repeated insert reused the observation. Rolling back all demo writes.")
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
