"""Public API contracts; mock records must never appear to be sourced observations."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Month = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$", description="Calendar month YYYY-MM (years 0001–9999)")]


class Provenance(BaseModel):
    source_name: str
    source_url: str | None = None
    source_publication_date: date | None = None
    source_vintage: str
    retrieved_at: datetime | None = None
    data_status: Literal["mock"] = "mock"
    geography: str
    covered_population: str
    methodology_notes: str


class PricePoint(BaseModel):
    observation_month: Month
    value: float = Field(ge=0, allow_inf_nan=False)


class PriceSeries(BaseModel):
    series_id: Literal["uranium_spot", "uranium_long_term"]
    label: str
    measure_type: Literal["price_indicator"] = "price_indicator"
    unit: Literal["USD/lb U3O8"] = "USD/lb U3O8"
    currency: Literal["USD"] = "USD"
    provenance: Provenance
    points: list[PricePoint]


class PriceHistory(BaseModel):
    from_month: Month | None
    to_month: Month | None
    series: list[PriceSeries]
    disclaimer: str


class LatestPrice(BaseModel):
    series_id: Literal["uranium_spot", "uranium_long_term"]
    label: str
    observation_month: Month
    value: float = Field(ge=0, allow_inf_nan=False)
    unit: Literal["USD/lb U3O8"] = "USD/lb U3O8"
    currency: Literal["USD"] = "USD"
    measure_type: Literal["price_indicator"] = "price_indicator"
    provenance: Provenance


class ContractingSnapshot(BaseModel):
    reporting_year: int = Field(ge=1, le=9999)
    value: int = Field(ge=0)
    unit: Literal["contracts"] = "contracts"
    measure_type: Literal["signed_contract_count"] = "signed_contract_count"
    provenance: Provenance


class MarketSummary(BaseModel):
    prices: list[LatestPrice]
    contracting: ContractingSnapshot
    freshness_status: Literal["mock_no_source_retrieved"] = "mock_no_source_retrieved"
    disclaimer: str
