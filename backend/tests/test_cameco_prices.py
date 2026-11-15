from argparse import ArgumentTypeError
from datetime import date
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import pytest

from app.ingestion.cameco_prices import SourceFormatError, parse_prices, parse_timestamp

FIXTURE = Path(__file__).parent / "fixtures" / "cameco_prices_synthetic.html"


def test_normalizes_months_decimals_missing_values_and_methodology():
    result = parse_prices(FIXTURE.read_text())
    assert len(result.observations) == 8
    assert result.duplicate_rows == 1
    assert result.warnings
    spot = next(point for point in result.observations if point.series_id == "uranium_spot" and point.observation_date.year == 2025)
    assert spot.observation_date == date(2025, 6, 1)
    assert spot.source_date == "2025/06/30"
    assert spot.raw_value == "76.00"
    assert spot.value == Decimal("76.00")
    missing = result.observations[1]
    assert missing.series_id == "uranium_long_term"
    assert missing.raw_value == ""
    assert missing.value is None
    assert "TradeTech only" in missing.methodology_notes
    assert "TradeTech only" not in result.observations[5].methodology_notes


@pytest.mark.parametrize("old,new", [
    ("Uranium Spot Price", "Renamed indicator"),
    ("2025/06/30", "2025/02/30"),
    ("76.00", "NaN"),
    ("76.00", "-1.00"),
    ("76.00", "76,00"),
    ("76.00", "76.001"),
    ("76.00", "-"),
    ("<td>83.00</td>", "<td></td>"),
    ("<td>76.00</td>", "<td></td>"),
    ("<td>76.00</td>", "<td>76.00</td><td>extra</td>"),
])
def test_unexpected_structure_or_values_fail_explicitly(old, new):
    with pytest.raises(SourceFormatError):
        parse_prices(FIXTURE.read_text().replace(old, new))


def test_conflicting_duplicate_is_not_silently_averaged():
    html = FIXTURE.read_text().replace("<td>76.00</td>", "<td>77.00</td>", 1)
    with pytest.raises(SourceFormatError, match="Conflicting duplicate"):
        parse_prices(html)


def test_one_month_with_different_source_day_is_still_a_duplicate():
    html = FIXTURE.read_text().replace("2025/06/30", "2025/06/01", 1)
    result = parse_prices(html)
    assert result.duplicate_rows == 1
    assert len(result.observations) == 8


@pytest.mark.parametrize("html", ["<html>Access denied</html>", "", "<table><tr><th></th><th>Uranium Spot Price</th><th>Long-term Uranium Price</th></tr></table>"])
def test_missing_or_empty_table_rejected(html):
    with pytest.raises(SourceFormatError):
        parse_prices(html)


def test_multiple_candidate_tables_rejected():
    with pytest.raises(SourceFormatError, match="exactly one"):
        parse_prices(FIXTURE.read_text() * 2)


def test_embedded_markup_whitespace_and_unrelated_tables():
    html = FIXTURE.read_text().replace("<td>76.00</td>", "<td>  <span>76.00</span>\n </td>")
    assert parse_prices(html).observations[-2].value == Decimal("76.00")


def test_retrieval_timestamp_requires_timezone():
    assert parse_timestamp("2026-11-15T13:00:00+01:00").isoformat() == "2026-11-15T12:00:00+00:00"
    with pytest.raises(ArgumentTypeError):
        parse_timestamp("2026-11-15T12:00:00")


def test_command_refuses_non_synthetic_file_without_permission():
    result = subprocess.run([sys.executable, "-m", "app.ingestion.cameco_prices", str(FIXTURE)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "actual permission reference" in result.stderr
