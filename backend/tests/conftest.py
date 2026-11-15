"""Shared isolated PostgreSQL schema, rolled back after each integration test."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db.connection import database_url


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

