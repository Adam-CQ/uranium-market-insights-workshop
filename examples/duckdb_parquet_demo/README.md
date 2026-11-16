# Milestone 8 — DuckDB and Parquet

The goal is to write a small, reproducible **synthetic** analytical snapshot,
query it with SQL, and compare its contents with our existing mock-price API.
No Cameco observations, downloads, PostgreSQL changes, or dashboard changes are
involved. The included CSV contains invented workshop values and may be kept
with the example code. Generated Parquet files stay under ignored
`data/processed/examples/`.

## Concept lesson

CSV stores rows as text. Parquet is a typed, compressed columnar file format:
values from the same column are stored together, making analytical column scans
useful without parsing every field as CSV text. It is a file, not a database
server. DuckDB is an in-process analytical SQL engine that can read/write those
files directly. Its Python package includes Parquet support, so pandas and
PyArrow are unnecessary for this example.

PostgreSQL remains the application's normalized operational store, including
relationships, import provenance and revision history. This six-row snapshot
has no ongoing synchronization with PostgreSQL or external publishers. It
illustrates a file boundary, not a replacement for the app's database or a
performance benchmark.

## Code map

- `mock_prices.csv`: six invented months matching the existing API fixture;
  includes units, currency, source name, and explicit `mock` status.
- `demo.py::write_snapshot`: validates/casts the CSV into a small typed in-memory
  DuckDB table, then writes ZSTD-compressed Parquet.
- `demo.py::read_snapshot`: opens a fresh in-memory DuckDB connection and queries
  the file by path. The file persists after the original connection closes.
- `backend/tests/test_examples.py`: round-trip/API parity, date filtering, quoted
  paths, and protection against overwriting existing files.

The output uses DATE and DECIMAL(12,2), so reading it yields Python `date` and
`Decimal` values. Observation dates use the first day as a monthly period label,
not a trade date. Unit is USD/lb U3O8; these are invented indicators.

## Run from the repository root

```bash
uv sync --directory backend --extra examples
uv run --project backend --extra examples python -m examples.duckdb_parquet_demo.demo
```

`--project backend` selects the uv-managed environment while leaving the working
directory at the repository root, where the `examples` module lives.
`--extra examples` includes the pinned optional DuckDB/websockets dependencies;
the core API does not require them.

Expected output includes six rows, starting with:

```text
SYNTHETIC TEACHING DATA — not Cameco observations or investment advice
2025-01-01 spot=70.00 long_term=80.00 USD/lb U3O8 [mock]
...
2025-06-01 spot=76.00 long_term=83.00 USD/lb U3O8 [mock]
Rows returned: 6
```

The default file is `data/processed/examples/mock_prices.parquet`. Verification
has already created it in this workspace. The writer deliberately refuses to
overwrite an existing output. Read it again, or choose a different new filename:

```bash
uv run --project backend --extra examples python -m examples.duckdb_parquet_demo.demo --read-only
uv run --project backend --extra examples python -m examples.duckdb_parquet_demo.demo --read-only --from-date 2025-04-01
uv run --project backend --extra examples python -m examples.duckdb_parquet_demo.demo --output data/processed/examples/another_mock_snapshot.parquet
```

The filtered read returns April, May, and June: spot values 74.00, 71.00, 76.00.
Paths supplied with `--output` are relative to your current working directory.
The writer publishes a complete temporary file using a same-filesystem hard
link; if a destination already exists, it fails without replacing its bytes.

## Small worked query

This query reads only the needed columns and orders monthly observations:

```sql
SELECT observation_date, spot_price
FROM read_parquet('data/processed/examples/mock_prices.parquet')
WHERE observation_date >= DATE '2025-04-01'
ORDER BY observation_date;
```

To execute the equivalent safely parameterized Python version, start
`uv run --project backend --extra examples python` from the root and paste:

```python
import duckdb
from datetime import date

with duckdb.connect(":memory:") as connection:
    rows = connection.execute(
        "SELECT observation_date, spot_price FROM read_parquet(?) "
        "WHERE observation_date >= ? ORDER BY observation_date",
        ["data/processed/examples/mock_prices.parquet", date(2025, 4, 1)],
    ).fetchall()
    print(rows)
```

`?` binds values rather than assembling SQL strings; even filenames containing
an apostrophe work. DuckDB can push column selection and filters into Parquet
scans. The six-row fixture demonstrates behavior, not a measurable speedup.

## Verify and review

```bash
uv run --directory backend --extra examples pytest tests/test_examples.py
```

The round-trip test compares every Parquet month and both prices with the
existing `GET /api/v1/prices/uranium` mock endpoint using an in-process client.
It also checks unit, currency, source, mock status, exact decimal values, date
filtering, and refusal to overwrite. It requires neither a live API server nor
PostgreSQL. The CSV/API parity test will flag future fixture drift.

Review checkpoint: explain which object is the SQL engine, which object is the
persistent file, why the values are still mock, and why the app continues to use
PostgreSQL. Inspect the file with DuckDB; do not expect a text editor to display
Parquet rows as it would CSV.

References: [DuckDB Parquet support](https://duckdb.org/docs/stable/data/parquet/overview),
[DuckDB Python DB API](https://duckdb.org/docs/stable/clients/python/dbapi).

Implementation checks passed: six-row write/read, exact mock-price API parity,
three-row April–June filtering, quoted filenames, and existing-output protection.
Both workshops' focused Python suite has 10 passing tests. The generated snapshot
is local/ignored; a clean checkout starts with the CSV and creates its own file.
