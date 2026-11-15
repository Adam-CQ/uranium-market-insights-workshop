"""Strict adapters for the reviewed EIA UMAR .xlsx Tables 7–10."""
import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.ingestion.cameco_prices import parse_timestamp

POPULATION = "Owners and operators of U.S. civilian nuclear power reactors"
SOURCE_NAME = "U.S. Energy Information Administration"
METHOD_VERSION = "eia-umar-xlsx-v1"
QUANTITY_UNIT = "thousand lb U3O8 equivalent"
PRICE_UNIT = "USD/lb U3O8 equivalent"
FILES = {7: "umartable7.xlsx", 8: "umartable8.xlsx", 9: "umartable9figure8.xlsx", 10: "umartable10figure9.xlsx"}
SHEETS = {7: "Table 7", 8: "Table 8", 9: "Table 9 and Figure 8", 10: "Table 10 and Figure 9"}
BASE_URL = "https://www.eia.gov/uranium/marketing/"
MAX_BYTES = 5_000_000


class WorkbookFormatError(ValueError):
    """Stop ingestion when workbook shape, units, or cells are unexpected."""


@dataclass(frozen=True)
class MetricDefinition:
    series_id: str
    label: str
    unit: str
    measure_type: str
    material_type: str | None = None
    supplier_scope: str | None = None
    quantity_bound: str | None = None


@dataclass(frozen=True)
class ContractFact:
    metric: MetricDefinition
    report_year: int
    delivery_year: int | None
    contract_type: str | None
    raw_value: str
    value: Decimal | None
    value_status: str
    cell: str


@dataclass(frozen=True)
class ParsedContracts:
    table: int
    report_year: int
    title: str
    release_label: str
    facts: tuple[ContractFact, ...]
    warnings: tuple[str, ...]


def definitions(table: int) -> dict[str, MetricDefinition]:
    result = {}
    def add(suffix, label, unit, measure, **dimensions):
        key = f"eia_t{table}_{suffix}"
        result[key] = MetricDefinition(key, label, unit, measure, **dimensions)
    if table == 7:
        for material in ["u3o8", "natural_uf6", "enriched_uranium", "total"]:
            add(f"{material}_quantity", f"Delivered quantity with reported price — {material}", QUANTITY_UNIT, "actual_deliveries_with_reported_price", material_type=material)
            add(f"{material}_price", f"Weighted-average delivery price — {material}", PRICE_UNIT, "weighted_average_delivery_price", material_type=material)
    elif table == 8:
        add("quantity", "Deliveries received in signing year under contracts signed that year", QUANTITY_UNIT, "same_year_deliveries_under_new_contracts")
        add("price", "Weighted-average price of signing-year deliveries under new contracts", PRICE_UNIT, "weighted_average_delivery_price_new_contracts")
        add("contract_count", "Contracts signed in reporting year with deliveries received that year", "contracts", "signed_contracts_with_same_year_deliveries")
    elif table in {9, 10}:
        for supplier in ([None] if table == 9 else ["us", "foreign", "all"]):
            for bound in ["minimum", "maximum"]:
                suffix = f"{supplier}_{bound}" if supplier else bound
                measure = "contracted_future_deliveries_new_signings" if table == 9 else "contracted_future_deliveries_in_effect"
                add(suffix, f"{bound.capitalize()} future contracted purchases" + (f" — {supplier} suppliers" if supplier else " — contracts signed in reporting year"), QUANTITY_UNIT, measure, supplier_scope=supplier, quantity_bound=bound)
    else:
        raise WorkbookFormatError("Supported EIA tables are 7, 8, 9, and 10")
    return result


def _text(value):
    return " ".join(str(value or "").split())


def parse_cell(cell, *, count=False):
    coordinate = getattr(cell, "coordinate", "blank cell")
    raw = "" if cell.value is None else str(cell.value).strip()
    if raw == "W":
        return raw, None, "withheld"
    if raw in {"", "--", "NA", "N/A"}:
        return raw, None, "missing"
    # Symbols are never silently interpreted as zero (including a single dash).
    if isinstance(cell.value, bool) or not isinstance(cell.value, (int, float, Decimal)):
        raise WorkbookFormatError(f"Unexpected numeric marker at {coordinate}: {raw!r}")
    try:
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value >= Decimal("1e16"):
            raise InvalidOperation
        if count and value != value.to_integral_value():
            raise WorkbookFormatError(f"Fractional contract count at {coordinate}")
        return raw, value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN), "available"
    except InvalidOperation as error:
        raise WorkbookFormatError(f"Invalid number at {coordinate}") from error


def parse_workbook(body: bytes, *, table: int, report_year: int) -> ParsedContracts:
    specs = definitions(table)
    if not 1900 <= report_year <= 9998 or len(body) > MAX_BYTES:
        raise WorkbookFormatError("Invalid report year or workbook exceeds 5 MB")
    try:
        with ZipFile(BytesIO(body)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 20_000_000:
                raise WorkbookFormatError("Expanded workbook exceeds 20 MB")
        book = load_workbook(BytesIO(body), data_only=False, read_only=True)
        cached = load_workbook(BytesIO(body), data_only=True, read_only=True)
    except (BadZipFile, OSError, KeyError, ValueError) as error:
        raise WorkbookFormatError("Expected a valid .xlsx workbook, not legacy .xls or HTML") from error
    try:
        if SHEETS[table] not in book.sheetnames:
            raise WorkbookFormatError(f"Missing reviewed sheet {SHEETS[table]!r}")
        sheet, values = book[SHEETS[table]], cached[SHEETS[table]]
        # Bound reads avoid accidentally scanning an entire malformed/large worksheet.
        rows = list(values.iter_rows(min_row=1, max_row=25, max_col=7))
        def cell(row, col):
            return rows[row - 1][col - 1]
        def text(row, col):
            return _text(cell(row, col).value)
        def expect(row, col, expected):
            if text(row, col) != expected:
                raise WorkbookFormatError(f"Unexpected header at row {row}, column {col}: expected {expected!r}")
        expect(1, 1, f"{report_year} Uranium Marketing Annual Report")
        title = text(5, 1)
        scope = "owners and operators of U.S. civilian nuclear power reactors"
        if not title.startswith(f"Table {table}.") or scope not in title:
            raise WorkbookFormatError("Unexpected table title or covered population")
        if table == 7:
            required = f"by contract type and material type, {report_year} deliveries"
        elif table == 8:
            required = f"Contracts signed in {report_year} "
        elif table == 9:
            required = f"signed in {report_year}, by delivery year"
        else:
            required = f"in effect at the end of {report_year}, by delivery year"
        if required not in title:
            raise WorkbookFormatError("Unexpected reporting year or measure definition in title")
        if table in {9, 10} and f"{report_year+1}-{report_year+10}" not in title.replace("–", "-"):
            raise WorkbookFormatError("Unexpected future-delivery horizon")
        expected_unit = "thousand pounds U3O8 equivalent"
        if table in {7, 8}:
            expected_unit += "; dollars per pound U3O8 equivalent"
        expect(6, 1, expected_unit)
        if not text(2, 1).startswith("Release Date:"):
            raise WorkbookFormatError("Missing workbook release label")
        if table == 7:
            expect(8, 1, "Material type")
            for col, header in [(2, "Spot contracts a"), (4, "Long-term contracts b"), (6, "Total")]:
                expect(8, col, header)
                expect(9, col, "Quantity with reported price")
                expect(9, col + 1, "Weighted-average price")
        elif table == 8:
            for col, header in enumerate([f"Purchase contract type (Signed in {report_year})", f"Quantity of deliveries received in {report_year}", "Weighted-average price", f"Number of purchase contracts for deliveries in {report_year}"], 1):
                expect(8, col, header)
        elif table == 9:
            for col, header in enumerate(["Year of delivery", "Minimum", "Maximum"], 1):
                expect(8, col, header)
        else:
            expect(8, 1, "Year of delivery")
            for col, supplier in [(2, "U.S."), (4, "foreign"), (6, "all")]:
                expect(8, col, f"Contracted purchases from {supplier} suppliers")
                expect(9, col, "Minimum")
                expect(9, col + 1, "Maximum")
        facts = []
        def add(row, col, suffix, delivery_year=None, contract_type=None):
            target = cell(row, col)
            formula = sheet.cell(row, col)
            if formula.data_type == "f" and target.value is None:
                raise WorkbookFormatError(f"Formula has no cached result at {formula.coordinate}")
            raw, value, status = parse_cell(target, count=suffix == "contract_count")
            facts.append(ContractFact(specs[f"eia_t{table}_{suffix}"], report_year, delivery_year, contract_type, raw, value, status, f"{get_column_letter(col)}{row}"))
        if table == 7:
            for row, label, material in [(10, "U3O8", "u3o8"), (11, "Natural UF6", "natural_uf6"), (12, "Enriched Uranium", "enriched_uranium"), (13, "Total", "total")]:
                expect(row, 1, label)
                for col, contract in [(2, "spot"), (4, "long_term"), (6, "total")]:
                    add(row, col, f"{material}_quantity", report_year, contract)
                    add(row, col + 1, f"{material}_price", report_year, contract)
            end_row = 13
        elif table == 8:
            for row, label, contract in [(9, "Spot", "spot"), (10, "Long-term", "long_term"), (11, "Total", "total")]:
                expect(row, 1, label)
                for col, suffix in [(2, "quantity"), (3, "price"), (4, "contract_count")]:
                    add(row, col, suffix, report_year, contract)
            end_row = 11
        else:
            start = 9 if table == 9 else 10
            for offset in range(11):
                row = start + offset
                year = report_year + 1 + offset if offset < 10 else None
                expect(row, 1, str(year) if year else "Total")
                if table == 9:
                    add(row, 2, "minimum", year)
                    add(row, 3, "maximum", year)
                else:
                    for col, supplier in [(2, "us"), (4, "foreign"), (6, "all")]:
                        add(row, col, f"{supplier}_minimum", year)
                        add(row, col + 1, f"{supplier}_maximum", year)
            end_row = start + 10
        if "Form EIA-858" not in text(end_row + 1, 1) or f"({report_year})" not in text(end_row + 1, 1):
            raise WorkbookFormatError("Missing survey/source attribution")
        warnings = _validate_totals(facts, table)
        if any(f.value_status == "missing" for f in facts):
            warnings.append("Missing cells retained as null; review before charting")
        return ParsedContracts(table, report_year, title, text(2, 1), tuple(facts), tuple(warnings))
    finally:
        book.close()
        cached.close()


def _validate_totals(facts, table):
    warnings = set()
    def check(parts, total):
        if any(f.value is None for f in [*parts, total]):
            warnings.add("Some totals cannot be checked because component values are withheld/missing; do not infer them")
            return
        tolerance = Decimal(0) if total.metric.unit == "contracts" else Decimal("0.5") * (len(parts) + 1)
        if abs(sum(f.value for f in parts) - total.value) > tolerance:
            raise WorkbookFormatError(f"Quantity/count total does not reconcile at {total.cell}")
    if table in {7, 8}:
        for spec in {f.metric for f in facts if f.metric.unit != PRICE_UNIT}:
            group = [f for f in facts if f.metric == spec]
            check([f for f in group if f.contract_type != "total"], next(f for f in group if f.contract_type == "total"))
        if table == 7:
            for contract in ["spot", "long_term", "total"]:
                group = [f for f in facts if f.metric.unit == QUANTITY_UNIT and f.contract_type == contract]
                check([f for f in group if f.metric.material_type != "total"], next(f for f in group if f.metric.material_type == "total"))
    else:
        for spec in {f.metric for f in facts}:
            group = [f for f in facts if f.metric == spec]
            check([f for f in group if f.delivery_year is not None], next(f for f in group if f.delivery_year is None))
        for minimum in [f for f in facts if f.metric.quantity_bound == "minimum"]:
            maximum = next(f for f in facts if f.delivery_year == minimum.delivery_year and f.metric.supplier_scope == minimum.metric.supplier_scope and f.metric.quantity_bound == "maximum")
            if minimum.value is not None and maximum.value is not None and minimum.value > maximum.value:
                raise WorkbookFormatError(f"Minimum exceeds maximum at {minimum.cell}")
        if table == 10:
            for year in {f.delivery_year for f in facts}:
                for bound in ["minimum", "maximum"]:
                    group = [f for f in facts if f.delivery_year == year and f.metric.quantity_bound == bound]
                    check([f for f in group if f.metric.supplier_scope != "all"], next(f for f in group if f.metric.supplier_scope == "all"))
    return sorted(warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--table", type=int, choices=FILES, required=True)
    parser.add_argument("--report-year", type=int, required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--retrieved-at", type=parse_timestamp)
    parser.add_argument("--publication-date", type=date.fromisoformat)
    parser.add_argument("--raw-dir", type=Path, default=Path("../data/raw/eia"))
    args = parser.parse_args()
    if args.input.stat().st_size > MAX_BYTES:
        parser.error("Workbook exceeds 5 MB")
    body = args.input.read_bytes()
    if args.write:
        if not args.retrieved_at or not args.publication_date:
            parser.error("--write requires actual --retrieved-at and --publication-date metadata")
        from app.db.connection import database_engine
        from app.ingestion.eia_repository import import_contracts
        engine = database_engine()
        try:
            result = import_contracts(engine, body, table=args.table, report_year=args.report_year,
                                      retrieved_at=args.retrieved_at, publication_date=args.publication_date, raw_dir=args.raw_dir)
        finally:
            engine.dispose()
    else:
        parsed = parse_workbook(body, table=args.table, report_year=args.report_year)
        result = {"table": parsed.table, "report_year": parsed.report_year,
                  "observations": len(parsed.facts), "population": POPULATION,
                  "warnings": parsed.warnings}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
