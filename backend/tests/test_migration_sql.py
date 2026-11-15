"""Offline compilation is useful but does not substitute for PostgreSQL tests."""
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_migration_compiles_for_postgresql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://offline:offline@localhost/offline")
    output = StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for table in ["data_source", "metric_definition", "ingestion_run", "market_observation"]:
        assert f"CREATE TABLE {table}" in sql
    assert "UNIQUE NULLS NOT DISTINCT" in sql
    assert "FOREIGN KEY(ingestion_run_id, source_id, artifact_sha256)" in sql
    assert "0001_provenance" in sql
