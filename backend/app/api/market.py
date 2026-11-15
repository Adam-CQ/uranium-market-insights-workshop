from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.market_fixture import DISCLAIMER, contracting_snapshot, price_series
from app.schemas import LatestPrice, MarketSummary, PriceHistory

router = APIRouter(prefix="/api/v1", tags=["Market preview"])
MonthQuery = r"^[0-9]{4}-(0[1-9]|1[0-2])$"


def validate_calendar_month(value: str | None, parameter: str) -> None:
    if value is not None:
        try:
            date.fromisoformat(f"{value}-01")
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{parameter} must be a valid YYYY-MM calendar month") from None


@router.get("/prices/uranium", response_model=PriceHistory)
def uranium_prices(
    from_month: Annotated[str | None, Query(alias="from", pattern=MonthQuery, description="Inclusive first month, YYYY-MM")] = None,
    to_month: Annotated[str | None, Query(alias="to", pattern=MonthQuery, description="Inclusive last month, YYYY-MM")] = None,
) -> PriceHistory:
    """Synthetic spot and long-term history. Empty ranges retain series metadata."""
    validate_calendar_month(from_month, "from")
    validate_calendar_month(to_month, "to")
    if from_month is not None and to_month is not None and from_month > to_month:
        raise HTTPException(status_code=422, detail="from must be earlier than or equal to to")
    series = price_series()
    for item in series:
        item.points = [
            point for point in item.points
            if (from_month is None or point.observation_month >= from_month)
            and (to_month is None or point.observation_month <= to_month)
        ]
    return PriceHistory(from_month=from_month, to_month=to_month, series=series, disclaimer=DISCLAIMER)


@router.get("/market/summary", response_model=MarketSummary)
def market_summary() -> MarketSummary:
    """Latest synthetic indicators and separately dated U.S. signing count."""
    return MarketSummary(
        prices=[
            LatestPrice(
                series_id=series.series_id,
                label=series.label,
                observation_month=series.points[-1].observation_month,
                value=series.points[-1].value,
                provenance=series.provenance,
            )
            for series in price_series()
        ],
        contracting=contracting_snapshot(),
        disclaimer=DISCLAIMER,
    )
