"""Deterministic synthetic fixture matching the Milestone 2 teaching preview."""
from app.schemas import ContractingSnapshot, PricePoint, PriceSeries, Provenance

DISCLAIMER = "Synthetic teaching data only; not Cameco or EIA observations. Educational market information, not investment advice."


def provenance(*, contracting: bool = False) -> Provenance:
    return Provenance(
        source_name="Synthetic teaching fixture",
        source_vintage="workshop-mock-v1",
        geography="United States" if contracting else "Global (illustrative only)",
        covered_population=(
            "U.S. civilian reactor owners/operators (illustrative only)"
            if contracting else "Illustrative uranium market indicators; no surveyed population"
        ),
        methodology_notes=(
            "Invented annual signing count, not deliveries or contracted volume. No EIA statistics are included."
            if contracting else
            "Invented monthly price indicators, not transaction prices. No Cameco observations are included."
        ),
    )


def price_series() -> list[PriceSeries]:
    months = [f"2025-{month:02d}" for month in range(1, 7)]
    return [
        PriceSeries(
            series_id=series_id,
            label=label,
            provenance=provenance(),
            points=[PricePoint(observation_month=month, value=value) for month, value in zip(months, values, strict=True)],
        )
        for series_id, label, values in [
            ("uranium_spot", "Spot price indicator — mock", [70, 68, 72, 74, 71, 76]),
            ("uranium_long_term", "Long-term price indicator — mock", [80, 80, 81, 81, 82, 83]),
        ]
    ]


def contracting_snapshot() -> ContractingSnapshot:
    return ContractingSnapshot(reporting_year=2024, value=12, provenance=provenance(contracting=True))
