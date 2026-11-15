"""PostgreSQL-only integration tests; opt in with TEST_DATABASE_URL."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from sqlalchemy.exc import IntegrityError

from app.db.connection import database_url
from app.db.demo import insert_fixture
from app.db.schema import metadata, observations


@pytest.fixture
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url and os.environ.get("RUN_POSTGRES_TESTS") == "1":
        url = database_url()
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or RUN_POSTGRES_TESTS=1 to run PostgreSQL tests")
    engine = sa.create_engine(url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = "test_" + uuid4().hex
                connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
                connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                yield connection
            finally:
                transaction.rollback()  # Includes the isolated schema and all DDL/data.
    finally:
        engine.dispose()


def test_clean_migration_matches_models(database):
    from alembic.migration import MigrationContext
    context = MigrationContext.configure(database)
    assert compare_metadata(context, metadata) == []


def test_fixture_join_and_idempotent_insert(database):
    first = insert_fixture(database)
    assert insert_fixture(database) == first
    row = database.execute(sa.select(observations).where(observations.c.id == first)).mappings().one()
    assert str(row["normalized_value"]) == "76.00000000"
    assert row["raw_value"] == "76.00"
    assert row["data_status"] == "mock"
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 1


@pytest.mark.parametrize("changes", [
    {},  # Duplicate even though report_year, delivery_year, and scenario are null.
    {"metric_id": -1},
    {"source_id": -1},
    {"ingestion_run_id": -1},
    {"artifact_sha256": "b" * 64},
    {"normalized_value": -1},
    {"value_status": "withheld"},  # Cannot retain a numeric value.
    {"normalized_value": None},  # Available requires a number.
    {"observation_date": None},
    {"delivery_year": 2030},  # Reporting year required.
])
def test_database_rejects_invalid_or_duplicate_records(database, changes):
    first = insert_fixture(database)
    row = dict(database.execute(sa.select(observations).where(observations.c.id == first)).mappings().one())
    row.pop("id")
    row.update(changes)
    with pytest.raises(IntegrityError), database.begin_nested():
        database.execute(observations.insert().values(**row))


def test_suppression_and_revision_preserve_history(database):
    first = insert_fixture(database)
    row = dict(database.execute(sa.select(observations).where(observations.c.id == first)).mappings().one())
    row.pop("id")
    row.update(report_year=2024, observation_date=None, delivery_year=2030,
               raw_value="W", normalized_value=None, value_status="withheld")
    database.execute(observations.insert().values(**row))
    # A revised observation uses a different artifact/run; the original stays intact.
    from app.db.schema import runs
    run = dict(database.execute(sa.select(runs).where(runs.c.id == row["ingestion_run_id"])).mappings().one())
    run.pop("id")
    run["artifact_sha256"] = "c" * 64
    revised_run = database.execute(runs.insert().values(**run).returning(runs.c.id)).scalar_one()
    row.update(artifact_sha256="c" * 64, ingestion_run_id=revised_run, supersedes_observation_id=first,
               observation_date=sa.literal_column("DATE '2025-06-30'"), report_year=None, delivery_year=None,
               raw_value="77.00", normalized_value=77, value_status="available", data_status="revised")
    database.execute(observations.insert().values(**row))
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 3
