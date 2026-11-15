"""Database-backed EIA read endpoints; never silently replace unavailable data with mocks."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import database_engine
from app.db.schema import metrics, observations, runs
from app.ingestion.eia_contracting import BASE_URL, POPULATION, SOURCE_NAME, definitions

router = APIRouter(prefix="/api/v1/contracts", tags=["EIA U.S. contracting"])


class ContractPoint(BaseModel):
    series_id: str
    label: str
    measure_type: str
    value: Decimal | None
    raw_value: str
    value_status: Literal["available", "withheld", "missing"]
    data_status: Literal["observed", "revised"]
    unit: str
    currency: str | None
    report_year: int
    delivery_year: int | None
    period_label: str
    contract_type: str | None
    material_type: str | None
    supplier_scope: str | None
    quantity_bound: str | None
    source_name: str = SOURCE_NAME
    source_url: str
    source_table: str
    source_publication_date: date
    source_vintage: str
    retrieved_at: datetime
    artifact_sha256: str
    ingestion_run_id: int
    quality_notes: str


class ContractResponse(BaseModel):
    scope: Literal["us"] = "us"
    geography: Literal["United States"] = "United States"
    covered_population: str = POPULATION
    table: int
    source_page: str
    data_status: Literal["available", "unavailable"]
    points: list[ContractPoint]
    caveats: list[str]


def contract_connection():
    try:
        engine = database_engine()
    except (RuntimeError, ValueError) as error:
        raise HTTPException(503, "Database is not configured for EIA data") from error
    try:
        with engine.connect() as connection:
            yield connection
    except SQLAlchemyError as error:
        raise HTTPException(503, "EIA data is unavailable; check database connection and migrations") from error
    finally:
        engine.dispose()


Connection = Annotated[sa.Connection, Depends(contract_connection)]
Scope = Annotated[Literal["us"], Query(description="U.S. civilian reactor owners/operators only")]
ReportYear = Annotated[int | None, Query(ge=1900, le=9998)]


def read_contracts(connection, table: int, report_year: int | None) -> ContractResponse:
    specs = definitions(table)
    # Resolve each fact by its latest inserted version, retaining separate reporting
    # years so Table 9/10 vintages are never stitched into one delivery forecast.
    ranked = sa.select(
        observations.c.id,
        sa.func.row_number().over(partition_by=[observations.c.metric_id, observations.c.report_year,
            observations.c.delivery_year, observations.c.contract_type], order_by=observations.c.id.desc()).label("rank"),
    ).join(metrics, observations.c.metric_id == metrics.c.id).where(metrics.c.series_id.in_(specs)).subquery()
    query = sa.select(
        observations, metrics.c.series_id, metrics.c.label, metrics.c.unit, metrics.c.currency, metrics.c.measure_type,
        runs.c.source_url, runs.c.source_table, runs.c.source_publication_date, runs.c.source_vintage, runs.c.retrieved_at,
    ).join(metrics, observations.c.metric_id == metrics.c.id).join(runs, observations.c.ingestion_run_id == runs.c.id).join(
        ranked, observations.c.id == ranked.c.id,
    ).where(ranked.c.rank == 1, runs.c.status == "succeeded").order_by(
        observations.c.report_year, metrics.c.series_id, observations.c.delivery_year, observations.c.contract_type,
    )
    if report_year is not None:
        query = query.where(observations.c.report_year == report_year)
    points = []
    for row in connection.execute(query).mappings():
        spec = specs[row["series_id"]]
        horizon = f"{row['report_year']+1}–{row['report_year']+10} total"
        points.append(ContractPoint(
            **{name: row[name] for name in ["series_id", "label", "measure_type", "raw_value", "value_status", "data_status", "unit", "currency", "report_year", "delivery_year", "contract_type", "source_url", "source_table", "source_publication_date", "source_vintage", "retrieved_at", "artifact_sha256", "ingestion_run_id", "quality_notes"]},
            value=row["normalized_value"], period_label=str(row["delivery_year"]) if row["delivery_year"] else horizon,
            material_type=spec.material_type, supplier_scope=spec.supplier_scope, quantity_bound=spec.quantity_bound,
        ))
    return ContractResponse(
        table=table, source_page=BASE_URL + f"table{table}.php",
        data_status="available" if points else "unavailable", points=points,
        caveats=[
            "U.S. civilian reactor owners/operators only; not global utility contracting.",
            "Table 8 counts only contracts signed in reporting year with deliveries received that year.",
            "W is withheld; missing and withheld values are null, never zero. Do not reconstruct suppressed data.",
            "Source quantities are thousand pounds U3O8 equivalent; weighted-average prices are separate measures.",
            "Totals overlap components; do not add totals to their components. Published values may be independently rounded.",
            "Tables 9/10 minimum and maximum are contractual bounds, not probabilistic scenarios. Keep reporting vintages separate.",
            "No matching observations means no successful import is available for this query; no mock fallback is returned.",
        ],
    )


@router.get("/signings", response_model=ContractResponse)
def signings(connection: Connection, scope: Scope = "us", report_year: ReportYear = None):
    """EIA Table 8: same-year deliveries, prices and counts under newly signed contracts."""
    return read_contracts(connection, 8, report_year)


@router.get("/future-deliveries", response_model=ContractResponse)
def future_deliveries(connection: Connection, scope: Scope = "us", report_year: ReportYear = None,
                      table: Annotated[Literal["9", "10"], Query()] = "9"):
    """Table 9 new signings or Table 10 existing contracts, by reporting/delivery year."""
    return read_contracts(connection, int(table), report_year)


@router.get("/deliveries", response_model=ContractResponse)
def deliveries(connection: Connection, scope: Scope = "us", report_year: ReportYear = None):
    """EIA Table 7: delivered quantities with reported price and weighted prices by material/type."""
    return read_contracts(connection, 7, report_year)
