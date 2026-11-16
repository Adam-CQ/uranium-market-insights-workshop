"""Write and query a synthetic Parquet snapshot using DuckDB alone."""
import argparse
from datetime import date
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

FIXTURE = Path(__file__).with_name("mock_prices.csv")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/examples/mock_prices.parquet"


def write_snapshot(output: Path) -> Path:
    """Validate the included CSV and publish Parquet without replacing any file."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists; choose another --output or use --read-only: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(":memory:") as connection:
        connection.execute("""
            CREATE TABLE mock_prices (
                observation_date DATE PRIMARY KEY,
                spot_price DECIMAL(12, 2) NOT NULL CHECK (spot_price >= 0),
                long_term_price DECIMAL(12, 2) NOT NULL CHECK (long_term_price >= 0),
                unit VARCHAR NOT NULL CHECK (unit = 'USD/lb U3O8'),
                currency VARCHAR NOT NULL CHECK (currency = 'USD'),
                source_name VARCHAR NOT NULL CHECK (source_name = 'Synthetic teaching fixture'),
                data_status VARCHAR NOT NULL CHECK (data_status = 'mock')
            )
        """)
        connection.execute("INSERT INTO mock_prices SELECT * FROM read_csv(?, header = true)", [str(FIXTURE)])
        # The temporary file and final output share a filesystem. A hard link
        # publishes complete bytes atomically and fails if the output already exists.
        with TemporaryDirectory(dir=output.parent, prefix=".duckdb-example-") as temporary:
            candidate = Path(temporary) / "prices.parquet"
            connection.execute("COPY mock_prices TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(candidate)])
            os.link(candidate, output)
    return output


def read_snapshot(path: Path, *, from_date: date = date(1, 1, 1)) -> list[dict]:
    """Query the file directly; an application database/server is not involved."""
    with duckdb.connect(":memory:") as connection:
        result = connection.execute("""
            SELECT observation_date, spot_price, long_term_price,
                   unit, currency, source_name, data_status
            FROM read_parquet(?)
            WHERE observation_date >= ?
            ORDER BY observation_date
        """, [str(path.resolve()), from_date])
        columns = [column[0] for column in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--read-only", action="store_true", help="Read an existing snapshot instead of writing")
    parser.add_argument("--from-date", type=date.fromisoformat, default=date(1, 1, 1))
    args = parser.parse_args()
    if not args.read_only:
        try:
            write_snapshot(args.output)
        except FileExistsError as error:
            parser.error(str(error))
    rows = read_snapshot(args.output, from_date=args.from_date)
    print("SYNTHETIC TEACHING DATA — not Cameco observations or investment advice")
    print(f"Parquet snapshot: {args.output.resolve()}")
    for row in rows:
        print(f"{row['observation_date']} spot={row['spot_price']:.2f} long_term={row['long_term_price']:.2f} {row['unit']} [{row['data_status']}]")
    print(f"Rows returned: {len(rows)}")
    print("PostgreSQL remains the dashboard's operational store. This file is an isolated analytical example.")


if __name__ == "__main__":
    main()
