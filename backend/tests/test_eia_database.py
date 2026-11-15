from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openpyxl import load_workbook
import pytest
import sqlalchemy as sa

from app.api.contracts import contract_connection
from app.db.schema import observations, runs
from app.ingestion.eia_contracting import WorkbookFormatError
from app.ingestion.eia_repository import import_contracts
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "eia"
TIME = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


@pytest.fixture
def importer(database, tmp_path):
    @contextmanager
    def begin():
        with database.begin_nested():
            yield database
    engine = SimpleNamespace(begin=begin)
    def run(table, body=None, when=TIME):
        return import_contracts(engine, body or (FIXTURES / f"table{table}_2025.xlsx").read_bytes(), table=table, report_year=2025, retrieved_at=when, publication_date=date(2026, 8, 13), raw_dir=tmp_path)
    return run


@pytest.fixture
def client(database):
    app.dependency_overrides[contract_connection] = lambda: database
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(contract_connection, None)


def test_all_tables_import_idempotently_and_keep_metadata(database, importer, tmp_path):
    for table, count in [(7, 24), (8, 9), (9, 22), (10, 66)]:
        assert importer(table)["added"] == count
        assert importer(table)["unchanged"] == count
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 121
    assert len(list(tmp_path.glob("*.xlsx"))) == 4
    assert database.scalar(sa.select(sa.func.count()).select_from(runs).where(runs.c.status == "succeeded")) == 8
    assert database.scalar(sa.select(runs.c.source_publication_date).limit(1)) == date(2026, 8, 13)


def test_api_separates_scope_periods_units_and_suppression(importer, client):
    for table in [7, 8, 9, 10]:
        importer(table)
    response = client.get("/api/v1/contracts/signings?scope=us&report_year=2025")
    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "us"
    assert data["geography"] == "United States"
    assert data["covered_population"] == "Owners and operators of U.S. civilian nuclear power reactors"
    counts = [point for point in data["points"] if point["unit"] == "contracts"]
    assert len(counts) == 3
    assert all("with deliveries received that year" in point["label"] for point in counts)
    total = next(point for point in counts if point["contract_type"] == "total")
    assert total["value"] == "22.00000000"
    assert total["report_year"] == total["delivery_year"] == 2025
    assert total["source_publication_date"] == "2026-08-13"
    assert len(total["artifact_sha256"]) == 64
    for table, count in [(9, 22), (10, 66)]:
        response = client.get(f"/api/v1/contracts/future-deliveries?scope=us&report_year=2025&table={table}")
        assert response.status_code == 200, response.text
        future = response.json()["points"]
        assert len(future) == count
        assert all(point["report_year"] == 2025 for point in future)
        assert all(point["delivery_year"] is None or point["delivery_year"] > 2025 for point in future)
        assert all(point["value"] is None for point in future if point["value_status"] == "withheld")
        assert any(point["period_label"] == "2026–2035 total" for point in future)
    delivery = client.get("/api/v1/contracts/deliveries?scope=us").json()
    assert len(delivery["points"]) == 24
    assert {point["material_type"] for point in delivery["points"]} == {"u3o8", "natural_uf6", "enriched_uranium", "total"}


def test_empty_and_invalid_queries_are_explicit(client):
    empty = client.get("/api/v1/contracts/signings?report_year=2025")
    assert empty.status_code == 200
    assert empty.json()["data_status"] == "unavailable"
    assert empty.json()["points"] == []
    for path in ["signings?scope=global", "deliveries?report_year=bad", "future-deliveries?table=8"]:
        assert client.get("/api/v1/contracts/" + path).status_code == 422


def test_revisions_and_failed_imports_are_atomic(database, importer, client):
    importer(8)
    book = load_workbook(FIXTURES / "table8_2025.xlsx")
    book.active["B9"] = 2902
    book.active["B11"] = 4322
    stream = BytesIO()
    book.save(stream)
    book.close()
    result = importer(8, stream.getvalue(), TIME + timedelta(days=1))
    assert result["revised"] == 2
    points = client.get("/api/v1/contracts/signings").json()["points"]
    assert len(points) == 9
    assert sum(point["data_status"] == "revised" for point in points) == 2
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 11
    assert importer(8)["revised"] == 0  # Replay old imported artifact does not undo revision.
    with pytest.raises(WorkbookFormatError):
        importer(9, b"invalid workbook")
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 11
    assert database.scalar(sa.select(sa.func.count()).select_from(runs).where(runs.c.status == "failed")) == 1
