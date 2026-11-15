import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import MarketSummary, PriceHistory


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_full_history_contract(client):
    response = client.get("/api/v1/prices/uranium")
    assert response.status_code == 200
    history = PriceHistory.model_validate(response.json())
    assert history.from_month is None and history.to_month is None
    assert [len(series.points) for series in history.series] == [6, 6]
    assert [series.points[-1].value for series in history.series] == [76, 83]
    for series in history.series:
        assert series.unit == "USD/lb U3O8"
        assert series.currency == "USD"
        assert series.provenance.data_status == "mock"
        assert series.provenance.source_url is None
        assert series.provenance.source_publication_date is None
        assert series.provenance.retrieved_at is None
    assert "not Cameco or EIA" in history.disclaimer


@pytest.mark.parametrize("query,months", [
    ("from=2025-04&to=2025-06", ["2025-04", "2025-05", "2025-06"]),
    ("from=2025-06", ["2025-06"]),
    ("to=2025-02", ["2025-01", "2025-02"]),
    ("from=2025-03&to=2025-03", ["2025-03"]),
    ("from=2030-01&to=2030-12", []),
])
def test_inclusive_ranges_and_empty_results(client, query, months):
    response = client.get(f"/api/v1/prices/uranium?{query}")
    assert response.status_code == 200
    for series in response.json()["series"]:
        assert [point["observation_month"] for point in series["points"]] == months
        assert series["provenance"]["data_status"] == "mock"
    # Filtering one response must not mutate data used by later requests.
    assert len(client.get("/api/v1/prices/uranium").json()["series"][0]["points"]) == 6


@pytest.mark.parametrize("query", [
    "from=2025-6", "to=2025-13", "from=not-a-date", "from=0000-01",
    "to=2025-02-01", "from=2025-06&to=2025-01", "from=",
])
def test_invalid_ranges_return_422(client, query):
    response = client.get(f"/api/v1/prices/uranium?{query}")
    assert response.status_code == 422
    assert response.json()["detail"]


def test_summary_preserves_separate_periods_and_us_scope(client):
    response = client.get("/api/v1/market/summary")
    assert response.status_code == 200
    summary = MarketSummary.model_validate(response.json())
    assert [price.value for price in summary.prices] == [76, 83]
    assert all(price.observation_month == "2025-06" for price in summary.prices)
    assert summary.contracting.reporting_year == 2024
    assert summary.contracting.value == 12
    assert summary.contracting.unit == "contracts"
    assert summary.contracting.measure_type == "signed_contract_count"
    assert summary.contracting.provenance.geography == "United States"
    assert "U.S. civilian reactor owners/operators" in summary.contracting.provenance.covered_population
    assert summary.freshness_status == "mock_no_source_retrieved"


def test_docs_expose_typed_responses_and_query_aliases(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    route = schema["paths"]["/api/v1/prices/uranium"]["get"]
    assert {parameter["name"] for parameter in route["parameters"]} == {"from", "to"}
    assert route["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PriceHistory")
