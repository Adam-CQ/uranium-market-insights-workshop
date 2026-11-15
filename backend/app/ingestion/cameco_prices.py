"""File-based Cameco HTML adapter. Live acquisition awaits source permission."""
import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re

SOURCE_URL = "https://www.cameco.com/invest/markets/uranium-price"
METHOD_VERSION = "cameco-html-v1"
HEADERS = ["", "Uranium Spot Price", "Long-term Uranium Price"]
SERIES = ("uranium_spot", "uranium_long_term")
MAX_BYTES = 5_000_000


class SourceFormatError(ValueError):
    """Source structure or values differ from the reviewed HTML contract."""


@dataclass(frozen=True)
class PriceObservation:
    series_id: str
    observation_date: date  # First day is a month identifier, not a transaction date.
    source_date: str
    raw_value: str
    value: Decimal | None
    methodology_notes: str


@dataclass(frozen=True)
class ParsedPrices:
    observations: tuple[PriceObservation, ...]
    duplicate_rows: int
    warnings: tuple[str, ...]


class _Tables(HTMLParser):
    """Read table text only; ignore unrelated markup, scripts, and navigation."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table = None
        self.row = None
        self.cell = None
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored_depth += 1
        if self.ignored_depth:
            return
        if tag == "table":
            if self.table is not None:
                raise SourceFormatError("Nested tables are unsupported")
            self.table = []
        elif self.table is not None:
            if tag == "tr":
                if self.row is not None:
                    raise SourceFormatError("Unclosed table row")
                self.row = []
            elif tag in {"th", "td"}:
                if self.row is None or self.cell is not None:
                    raise SourceFormatError("Unexpected table cell")
                self.cell = []

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored_depth = max(0, self.ignored_depth - 1)
            return
        if self.ignored_depth:
            return
        if tag in {"th", "td"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cell is not None:
                raise SourceFormatError("Unclosed table cell")
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.row is not None:
                raise SourceFormatError("Unclosed table row")
            self.tables.append(self.table)
            self.table = None

    def handle_data(self, data):
        if self.cell is not None and not self.ignored_depth:
            self.cell.append(data)


def parse_prices(html: str) -> ParsedPrices:
    parser = _Tables()
    parser.feed(html)
    parser.close()
    if parser.table is not None:
        raise SourceFormatError("Unclosed table")
    candidates = [table for table in parser.tables if table and table[0] == HEADERS]
    if len(candidates) != 1:
        raise SourceFormatError("Expected exactly one historical table with reviewed price headers")
    rows = candidates[0][1:]
    if not rows:
        raise SourceFormatError("Historical price table is empty")
    by_month = {}
    duplicates = 0
    for row in rows:
        if len(row) != 3:
            raise SourceFormatError("Historical rows must have date, spot, and long-term cells")
        raw_date = row[0]
        if not re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}", raw_date):
            raise SourceFormatError(f"Unexpected source date: {raw_date!r}")
        try:
            source_date = date.fromisoformat(raw_date.replace("/", "-"))
        except ValueError as error:
            raise SourceFormatError(f"Invalid source date: {raw_date!r}") from error
        month = source_date.replace(day=1)
        values = []
        for raw_value in row[1:]:
            if raw_value == "":
                values.append(None)
            elif re.fullmatch(r"[0-9]+\.[0-9]{2}", raw_value):
                value = Decimal(raw_value)
                if value >= Decimal("1e16"):
                    raise SourceFormatError("Price exceeds database precision")
                values.append(value)
            else:
                raise SourceFormatError(f"Unexpected price text: {raw_value!r}")
        if values[0] is None:
            raise SourceFormatError("Spot price cannot be blank in a historical row")
        if values[1] is None and month >= date(1996, 3, 1):
            raise SourceFormatError("Unexpected blank long-term price after historical coverage starts")
        if month in by_month:
            if by_month[month][1] != tuple(values):
                raise SourceFormatError(f"Conflicting duplicate month: {month:%Y-%m}")
            duplicates += 1
            continue
        by_month[month] = (raw_date, tuple(values), tuple(row[1:]))
    result = []
    for month, (raw_date, values, raw_values) in sorted(by_month.items()):
        for series, raw_value, value in zip(SERIES, raw_values, values, strict=True):
            notes = (
                "Published monthly market indicator, not a transaction price. "
                "Month-end UxC/TradeTech inputs averaged by Cameco. "
                "observation_date uses the first day only to identify the month. "
                f"Source date label: {raw_date}."
            )
            if series == "uranium_long_term" and month < date(2004, 5, 1):
                notes += " Before May 2004: TradeTech only, not an industry average."
            if value is None:
                notes += " Historical long-term value absent; not zero."
            result.append(PriceObservation(series, month, raw_date, raw_value, value, notes))
    warnings = (f"Collapsed {duplicates} identical duplicate monthly row(s)",) if duplicates else ()
    return ParsedPrices(tuple(result), duplicates, warnings)


def parse_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timezone required")
        return timestamp.astimezone(timezone.utc)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use an ISO timestamp with timezone, e.g. 2026-11-15T12:00:00Z") from error


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Local HTML file; no network request is made")
    parser.add_argument("--synthetic", action="store_true", help="Use only invented test data; stores under separate mock series")
    parser.add_argument("--permission-reference", help="Reference to actual source permission covering this use; not permission by itself")
    parser.add_argument("--retrieved-at", type=parse_timestamp, help="Actual acquisition timestamp, required for non-synthetic files")
    parser.add_argument("--publication-date", type=date.fromisoformat, help="Only if explicitly stated by source; otherwise remains unknown")
    parser.add_argument("--write", action="store_true", help="Import into PostgreSQL; default only parses a permitted file")
    parser.add_argument("--raw-dir", type=Path, default=Path("../data/raw/cameco"))
    args = parser.parse_args()
    if not args.synthetic and (not args.permission_reference or not args.retrieved_at):
        parser.error("Non-synthetic files require actual permission reference and acquisition timestamp; see data/README.md")
    if args.input.stat().st_size > MAX_BYTES:
        parser.error("HTML file exceeds 5 MB limit")
    body = args.input.read_bytes()
    if args.write:
        from app.db.connection import database_engine
        from app.ingestion.price_repository import import_prices
        engine = database_engine()
        try:
            result = import_prices(
                engine, body, retrieved_at=args.retrieved_at or datetime.now(timezone.utc),
                raw_dir=args.raw_dir, synthetic=args.synthetic,
                permission_reference=args.permission_reference,
                publication_date=args.publication_date,
            )
            print(json.dumps(result, indent=2))
        finally:
            engine.dispose()
    else:
        parsed = parse_prices(body.decode("utf-8"))
        print(json.dumps({"observations": len(parsed.observations), "warnings": parsed.warnings,
                          "data_status": "mock" if args.synthetic else "observed",
                          "first_month": str(parsed.observations[0].observation_date),
                          "last_month": str(parsed.observations[-1].observation_date)}, indent=2))


if __name__ == "__main__":
    main()
