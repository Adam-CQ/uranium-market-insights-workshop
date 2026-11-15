# Source artifacts, provenance, and refresh

For EIA Tables 7–10, see [the EIA workbook guide](eia.md): permitted public-data
downloads, imports, definitions, and contracting endpoints. Cameco remains
synthetic pending permission; the sections below describe that separate source.

## Cameco source review — 2026-11-15

- Public historical table: https://www.cameco.com/invest/markets/uranium-price
- Methodology: Cameco publishes indicators calculated from month-end UxC and
  TradeTech inputs. Before May 2004, long-term values use TradeTech only.
  These are published indicators, not prices for every privately negotiated sale.
- Current HTML contains one three-column historical table with headers
  `Uranium Spot Price` and `Long-term Uranium Price`. It is the data table used
  by the public chart, not an undocumented API. The adapter does not execute JS.
- Historical date labels include first-of-month and end-of-month dates. We store
  the first day as a monthly period identifier, retaining source labels in notes
  and the unchanged HTML artifact. It must not be described as a trade date.
- Identical duplicate monthly rows exist on the reviewed page. Collapse identical
  values with a run warning; conflicting duplicates must fail rather than average.
- Long-term history is blank before March 1996. Preserve these as missing values.
  A blank spot value or a new blank long-term value after coverage begins fails
  for review. Missing values are not zero and are never interpolated.
- The HTML table does not label currency/unit. US dollars per pound U3O8 is
  cross-checked against Cameco's 2025 Annual Information Form (term-price table)
  and annual report (industry-average price discussion), not extracted from a
  nonexistent table label:
  https://www.cameco.com/sites/default/files/documents/Cameco%202025%20Annual%20Information%20Form.pdf
  https://www.cameco.com/sites/default/files/documents/cameco-2025-annual-report.pdf
  Normalized unit is `USD/lb U3O8`, currency `USD`; no conversion is performed.
- No publication date was established for the entire history. It remains null.
  The final observation date and retrieval time are separate concepts. Source
  vintage is the raw file's SHA-256, not an invented report publication date.

## Permission finding and current boundary

https://www.cameco.com/terms-of-use grants unaltered personal/noncommercial
viewing or printing and requires prior written consent for other uses. It does
not establish permission for this application's ingestion or redistribution.
The reviewed https://www.cameco.com/robots.txt does not disallow the price-page
path, but robots permission is not a reuse licence.

Therefore this repository provides a **file-based adapter tested with invented
data**, with no live downloader or scheduled job. It contains no Cameco historical
extract, copied page markup, charts, or proprietary UxC/TradeTech dataset. The
fixture's values and minimal markup were independently written to exercise the
reviewed column layout. This differs from a sanitized copy of a real source
page because permission to redistribute such a copy has not been established.

Do not import real Cameco material until permission covers acquisition,
normalization/storage, and intended display. `--permission-reference` records
an actual permission document/reference; supplying a string does not grant
permission. `--synthetic` is only for invented values and writes separate mock
series with mock status. It must not be used to relabel downloaded prices.
Public deployment and real source validation remain pending permission.

## Try the synthetic parser

From the repository root (no database or new dependency needed):

```bash
uv run --directory backend python -m app.ingestion.cameco_prices \
  tests/fixtures/cameco_prices_synthetic.html --synthetic
uv run --directory backend pytest tests/test_cameco_prices.py
```

Expected parser summary: 8 observations (4 months × 2 series), including one
explicitly missing long-term value, and a warning about one duplicate row.
The fixture deliberately samples widely separated dates to test methodology
boundaries; it is not a continuous history. The parser is strict about date,
header, cell-count, and two-decimal price formats. Unexpected layouts fail.

Worked row: invented `2025/06/30 | 76.00 | 83.00` yields two typed observations.
Spot has monthly period `2025-06-01`, original label `2025/06/30`, raw text
`76.00`, normalized `Decimal('76.00')`, unit `USD/lb U3O8`, and currency `USD`.
A synthetic import adds mock status, a local artifact checksum, and a run time;
that time is not claimed as an external source retrieval.

## Try persistence in PostgreSQL

Export your existing local `POSTGRES_PASSWORD` as described in the root README.
Use the existing volume password. From the repository root:

```bash
docker compose up --build -d db api
docker compose exec api uv run --locked --no-dev alembic upgrade head
mkdir -p data/raw/cameco
docker compose run --rm --no-deps -T \
  -v "$PWD/backend/tests/fixtures:/fixtures:ro" \
  -v "$PWD/data/raw/cameco:/data/raw/cameco" \
  api uv run --locked --no-dev python -m app.ingestion.cameco_prices \
  /fixtures/cameco_prices_synthetic.html --synthetic --write \
  --raw-dir /data/raw/cameco
```

This command intentionally **persists synthetic records**. Run it twice: the
first import adds 8 observations; the second adds none and reports 8 unchanged.
Each attempt has a separate ingestion-run row. It never updates the API mock
fixture or frontend. To test without persistent records, use the integration
suite below, which rolls back its isolated schemas and uses temporary artifacts.

```bash
docker compose run --rm --no-deps -T -e RUN_POSTGRES_TESTS=1 \
  -v "$PWD/backend/tests:/app/tests:ro" \
  api uv run --locked pytest tests
```

Verification on 2026-11-15: **56 tests passed** against PostgreSQL, including
existing API and migration tests. The only warning is the previously known
Starlette/HTTPX deprecation. Source values have not been imported; real-value
comparison and live ingestion remain pending permission.

## Refresh workflow after permission is established

1. Recheck source terms, permission scope, robots policy, HTML headers, dates,
   and unit evidence. No live downloader is provided while rights are unresolved.
2. Save the permitted public HTML manually, record its real acquisition time,
   and retain the original bytes privately. A provider's HTTP/page metadata must
   not be substituted silently for a known source publication date.
3. Preview the permitted file through the adapter, recording actual permission
   and timestamp. Example shape (replace these placeholders, do not treat this
   command as authorisation):

   ```bash
   uv run --directory backend python -m app.ingestion.cameco_prices \
     /absolute/path/to/permitted-prices.html \
     --permission-reference 'your actual permission reference' \
     --retrieved-at '2026-11-15T12:00:00Z'
   ```

4. Once the preview is verified, run with `--write --raw-dir /absolute/private/raw`.
   This requires the existing database connection configuration. In a container,
   bind the input file read-only and bind an artifact directory so stored raw
   files survive container removal. Supply `--publication-date YYYY-MM-DD` only
   when supported by the source; otherwise leave it unknown.
5. Compare a small sample visually against the official table, including an early
   blank long-term value, pre/post-May-2004 methodology, and the latest month.
   Run the offline parser tests after any parser changes. Check run status/notes.
6. Refresh manually at monthly cadence; do not imply real-time updates. Review
   changed values and missing months before exposing the data in the application.

The importer stores raw HTML by SHA-256 filename, uses a transaction-scoped
PostgreSQL advisory lock, and writes each successful batch atomically. An exact
successful artifact replay adds no observations. An unrelated page edit also
adds no observations when parsed values are unchanged. A changed value from a
newer acquisition links to the previous observation without overwriting it.
Replaying an already imported old artifact does not revert the current value.
An unrecognized older changed snapshot or disappeared historical month aborts
for review. Failure rolls back observation writes and marks the run failed.
Acquisition/file-system errors before a run can be created appear as command
errors, not database run records. These commands have no automatic retry loop.

Raw date/value text remains in the artifact; normalized records preserve numeric
text and original date in notes. Formatting-only changes are retained in the new
artifact/run but do not create a new value revision. Never rewrite historical
rows to change units or silently delete missing months. A future database read
adapter must resolve revision chains and freshness from ingestion runs; the
current dashboard/API intentionally remain synthetic until integration.

## Local files and repository hygiene

- `data/raw/`: local source files; ignored by Git. The importer does not upload them.
- `data/processed/`: future Parquet snapshots; ignored by Git.
- `backend/tests/fixtures/cameco_prices_synthetic.html`: small invented fixture,
  permitted to include with project code, not a Cameco extract.

Do not force-add licensed/private source files. Retention and redistribution
must match the eventual permission, including any raw-file restrictions.
