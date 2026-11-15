"""Read connection settings only when explicitly running a database command."""
import os

from sqlalchemy import URL, create_engine


def database_url() -> str | URL:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("Set DATABASE_URL or POSTGRES_PASSWORD before running database commands")
    return URL.create(
        "postgresql+psycopg", username="dashboard", password=password,
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")), database="uranium",
    )


def database_engine():
    return create_engine(database_url(), pool_pre_ping=True)
