"""Isolated optional workshops. Run with uv's --extra examples flag."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("duckdb", reason="Run with --extra examples to test the optional workshops")
pytest.importorskip("websockets", reason="Run with --extra examples to test the optional workshops")

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from pydantic import ValidationError

from app.main import app as dashboard_app
from examples.duckdb_parquet_demo.demo import read_snapshot, write_snapshot
from examples.websocket_demo.server import MockMessage, create_app, make_message


def test_parquet_round_trip_matches_existing_mock_price_api(tmp_path):
    snapshot = write_snapshot(tmp_path / "prices.parquet")
    rows = read_snapshot(snapshot)
    with TestClient(dashboard_app) as client:
        response = client.get("/api/v1/prices/uranium")
    assert response.status_code == 200
    source = {series["series_id"]: series for series in response.json()["series"]}
    assert len(rows) == 6
    for row, spot, term in zip(rows, source["uranium_spot"]["points"], source["uranium_long_term"]["points"], strict=True):
        assert row["observation_date"].strftime("%Y-%m") == spot["observation_month"] == term["observation_month"]
        assert row["spot_price"] == Decimal(str(spot["value"]))
        assert row["long_term_price"] == Decimal(str(term["value"]))
        assert row["unit"] == source["uranium_spot"]["unit"]
        assert row["currency"] == "USD"
        assert row["data_status"] == "mock"
        assert row["source_name"] == "Synthetic teaching fixture"


def test_parquet_filter_and_filename_with_apostrophe(tmp_path):
    snapshot = write_snapshot(tmp_path / "learner's prices.parquet")
    filtered = read_snapshot(snapshot, from_date=date(2025, 4, 1))
    assert [row["observation_date"] for row in filtered] == [date(2025, 4, 1), date(2025, 5, 1), date(2025, 6, 1)]
    assert [row["spot_price"] for row in filtered] == [Decimal("74.00"), Decimal("71.00"), Decimal("76.00")]


def test_existing_output_is_never_overwritten(tmp_path):
    target = tmp_path / "keep.parquet"
    target.write_bytes(b"existing user file")
    with pytest.raises(FileExistsError):
        write_snapshot(target)
    assert target.read_bytes() == b"existing user file"


def test_websocket_push_disconnect_and_new_connection():
    with TestClient(create_app(interval_seconds=0.01)) as client:
        assert client.get("/").status_code == 200
        assert "not a real-time uranium feed" in client.get("/").text
        assert client.get("/client.js").status_code == 200
        with client.websocket_connect("/ws/mock") as connection:
            first = MockMessage.model_validate(connection.receive_json())
            second = MockMessage.model_validate(connection.receive_json())
            assert first.sequence == 1 and first.value == 100.0
            assert second.sequence == 2 and second.value == 100.25
            assert first.data_status == "mock"
            assert second.connection_id == first.connection_id
        with client.websocket_connect("/ws/mock") as connection:
            reconnected = MockMessage.model_validate(connection.receive_json())
            assert reconnected.sequence == 1
            assert reconnected.connection_id != first.connection_id


@pytest.mark.parametrize("changes", [
    {"sequence": 0}, {"sequence": True}, {"value": float("nan")},
    {"data_status": "observed"}, {"extra": "unrecognized"},
])
def test_mock_message_contract_rejects_invalid_payloads(changes):
    payload = make_message(1, uuid4()).model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        MockMessage.model_validate(payload)


def test_demo_route_is_absent_from_dashboard_application():
    with TestClient(dashboard_app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/mock"):
                pytest.fail("The dashboard unexpectedly accepted the isolated demo route")
        assert client.get("/").status_code == 404
        assert client.get("/health").json() == {"status": "ok"}
