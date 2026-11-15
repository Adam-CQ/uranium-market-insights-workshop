from decimal import Decimal
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
import pytest

from app.ingestion.eia_contracting import PRICE_UNIT, QUANTITY_UNIT, WorkbookFormatError, parse_workbook

FIXTURES = Path(__file__).parent / "fixtures" / "eia"


def workbook(table):
    return (FIXTURES / f"table{table}_2025.xlsx").read_bytes()


def changed(table, coordinate, value):
    book = load_workbook(BytesIO(workbook(table)))
    book.active[coordinate] = value
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


@pytest.mark.parametrize("table,count", [(7, 24), (8, 9), (9, 22), (10, 66)])
def test_offline_source_workbooks(table, count):
    parsed = parse_workbook(workbook(table), table=table, report_year=2025)
    assert parsed.table == table
    assert len(parsed.facts) == count
    assert all(fact.report_year == 2025 for fact in parsed.facts)
    assert all(fact.metric.unit in {PRICE_UNIT, QUANTITY_UNIT, "contracts"} for fact in parsed.facts)


def test_table8_qualifier_counts_quantities_and_prices_are_separate():
    parsed = parse_workbook(workbook(8), table=8, report_year=2025)
    total = {fact.metric.series_id: fact for fact in parsed.facts if fact.contract_type == "total"}
    assert total["eia_t8_contract_count"].value == 22
    assert "with deliveries received that year" in total["eia_t8_contract_count"].metric.label
    assert total["eia_t8_quantity"].value == 4321
    assert total["eia_t8_quantity"].metric.unit == QUANTITY_UNIT
    assert total["eia_t8_price"].value == Decimal("70.46000000")
    assert all(fact.delivery_year == 2025 for fact in parsed.facts)
    assert not parsed.warnings


def test_table9_retains_two_years_bounds_and_withheld_values():
    parsed = parse_workbook(workbook(9), table=9, report_year=2025)
    first = parsed.facts[0]
    assert (first.report_year, first.delivery_year) == (2025, 2026)
    assert first.metric.quantity_bound == "minimum"
    assert first.value == 1511
    withheld = next(fact for fact in parsed.facts if fact.delivery_year == 2033)
    assert withheld.raw_value == "W"
    assert withheld.value is None
    assert withheld.value_status == "withheld"
    assert parsed.facts[-1].delivery_year is None  # Published horizon total, not a made-up year.
    assert parsed.warnings


def test_table7_material_categories_and_workbook_precision():
    parsed = parse_workbook(workbook(7), table=7, report_year=2025)
    assert {fact.metric.material_type for fact in parsed.facts} == {"u3o8", "natural_uf6", "enriched_uranium", "total"}
    first = parsed.facts[0]
    assert first.value == Decimal("5679.50000000")  # Web table independently rounds this to 5680.
    assert "with reported price" in first.metric.label
    assert first.metric.measure_type == "actual_deliveries_with_reported_price"


def test_table10_supplier_dimensions_and_total():
    parsed = parse_workbook(workbook(10), table=10, report_year=2025)
    assert {fact.metric.supplier_scope for fact in parsed.facts} == {"us", "foreign", "all"}
    maximum = next(fact for fact in parsed.facts if fact.delivery_year is None and fact.metric.supplier_scope == "all" and fact.metric.quantity_bound == "maximum")
    assert maximum.value == 174095


@pytest.mark.parametrize("marker", [None, "--", "NA", "N/A"])
def test_missing_value_is_not_zero(marker):
    parsed = parse_workbook(changed(9, "B9", marker), table=9, report_year=2025)
    assert parsed.facts[0].value is None
    assert parsed.facts[0].value_status == "missing"
    assert any("Missing cells" in warning for warning in parsed.warnings)


@pytest.mark.parametrize("coordinate,value", [
    ("A1", "2024 Uranium Marketing Annual Report"),
    ("A5", "Table 8. global market signings"),
    ("A6", "million pounds"),
    ("B8", "All signed quantities"),
    ("D9", 1.5),
    ("B9", -1),
    ("B9", "unexpected"),
    ("B9", "-"),
    ("D9", "=17"),
    ("D11", 23),
])
def test_changed_definitions_bad_values_uncached_formulas_and_totals_fail(coordinate, value):
    with pytest.raises(WorkbookFormatError):
        parse_workbook(changed(8, coordinate, value), table=8, report_year=2025)


def test_minimum_cannot_exceed_maximum():
    with pytest.raises(WorkbookFormatError):
        parse_workbook(changed(9, "B9", 2000), table=9, report_year=2025)


def test_wrong_delivery_year_and_non_workbook_fail():
    with pytest.raises(WorkbookFormatError):
        parse_workbook(changed(9, "A9", 2027), table=9, report_year=2025)
    with pytest.raises(WorkbookFormatError):
        parse_workbook(b"<html>Access denied</html>", table=9, report_year=2025)
