# EIA contracting: download, import, and verify

## Scope and reuse

Source: U.S. Energy Information Administration (EIA), *Uranium Marketing Annual
Report*, 2025 data, report released July 29, 2026 and re-released August 13, 2026.

- [Report and official XLS links](https://www.eia.gov/uranium/marketing/index.php)
- [Report revision notice](https://www.eia.gov/uranium/marketing/includes/revision-notice.php)
- [EIA copyright and reuse policy](https://www.eia.gov/about/copyrights_reuse.php)
- [EIA robots policy](https://www.eia.gov/robots.txt)

EIA allows reuse of its government data with acknowledgement, including the
publication date. These are Form EIA-858 survey tables, not third-party images or
logos. The reviewed robots policy allows the workbook paths. Unlike Cameco,
these tables can be imported under the published reuse policy. Attribute EIA;
do not imply endorsement or use its logo. Check policies before later refreshes.

The population is **owners and operators of U.S. civilian nuclear power reactors**,
not all global utilities. Supplier origin in Table 10 does not change this U.S.
buyer population. Quantities use **thousand pounds U3O8 equivalent**, not pounds,
million pounds, enriched-material mass, or Cameco's price indicator unit.
Prices are weighted-average delivery prices in **USD/lb U3O8 equivalent** and
are not inflation-adjusted. No scale conversion is performed.

## Four distinct measures

| Table | Meaning | Periods and dimensions |
| --- | --- | --- |
| [7](https://www.eia.gov/uranium/marketing/table7.php) | Delivered quantities **with reported price**, and weighted-average delivery prices | Reporting year and actual delivery year; spot/long-term/total contracts; U3O8/natural UF6/enriched uranium/total material |
| [8](https://www.eia.gov/uranium/marketing/table8.php) | Contracts signed in reporting year **with deliveries received that year**: quantity, weighted price, count | Signing/report year and same-year delivery; spot/long-term/total contracts |
| [9](https://www.eia.gov/uranium/marketing/table9.php) | Future purchases under contracts signed in reporting year | Reporting year and future delivery year; minimum/maximum; published horizon totals |
| [10](https://www.eia.gov/uranium/marketing/table10.php) | Future purchases under contracts already in effect at reporting year-end | Reporting year and future delivery year; U.S./foreign/all suppliers; minimum/maximum; published horizon totals |

Table 8 is **not a complete count of all contracts signed in the year regardless
of first delivery**. Do not relabel it as global contracting. EIA's definition of
spot is usually a one-time delivery within one year of signing; long-term means
one or more deliveries at least a year after signing. These definitions remain
in metric methodology notes.

Minimum and maximum are contractual quantity bounds, not probability scenarios.
Totals and their components overlap. Never add the total row to its components,
combine report vintages into one future delivery curve, sum weighted-average
prices, or merge delivered uranium with new signings.

## Download current official workbooks

The report labels links “XLS”, but the reviewed downloads are `.xlsx` files.
`openpyxl` reads them; older binary `.xls` files are explicitly unsupported.
The parser supports the reviewed layout and checks report year, sheet name,
units, headers, categories, delivery horizon, and source attribution. It fails
for review if those definitions change rather than guessing.

The links below currently serve 2025 data, but EIA may update these stable URLs
for the next annual report. **Read the landing page first**, verify the reporting
year and applicable publication/re-release date, and retain that report vintage.
The August 13 re-release applies to the report; it does not imply every table
changed on that date. Workbook release labels still say July 2026 and are
preserved separately in observation notes.

From the repository root:

```bash
mkdir -p data/raw/eia/downloads
for eia_filename in umartable7.xlsx umartable8.xlsx umartable9figure8.xlsx umartable10figure9.xlsx; do
  curl --fail --location --output "data/raw/eia/downloads/$eia_filename" \
    "https://www.eia.gov/uranium/marketing/xls/$eia_filename" || break
  date -u +'%Y-%m-%dT%H:%M:%SZ' > "data/raw/eia/downloads/$eia_filename.retrieved-at.txt"
  sha256sum "data/raw/eia/downloads/$eia_filename"
done
```

`--fail` rejects HTTP errors and `--location` follows ordinary redirects. The
sidecars record the time each download completed, not its publication date.
Do not run this continuously; these are annual tables. On a future refresh,
retain prior downloads privately before replacing named download files.
Successful imports retain checksum-named originals beside them.

Preview one workbook without touching PostgreSQL:

```bash
uv sync --directory backend --locked
uv run --directory backend python -m app.ingestion.eia_contracting \
  ../data/raw/eia/downloads/umartable9figure8.xlsx --table 9 --report-year 2025
```

Expected: Table 9, reporting year 2025, U.S. population, 22 observations, and a
warning that withheld components prevent checking some totals. The other
reviewed workbooks yield Table 7: 24, Table 8: 9, Table 10: 66 observations.
Counts include separate measures and published totals, not just annual bars.

## Import with Compose

Export the **existing** `POSTGRES_PASSWORD` as described in the root README.
No `.env` changes are required. Build the API with the approved workbook reader:

```bash
docker compose up --build -d db api
docker compose exec api uv run --locked --no-dev alembic upgrade head
```

Import the four files, using the report metadata you verified above:

```bash
for eia_pair in '7 umartable7.xlsx' '8 umartable8.xlsx' '9 umartable9figure8.xlsx' '10 umartable10figure9.xlsx'; do
  read -r eia_table eia_filename <<< "$eia_pair"
  eia_retrieved_at=$(cat "data/raw/eia/downloads/$eia_filename.retrieved-at.txt")
  docker compose run --rm --no-deps -T \
    -v "$PWD/data/raw/eia:/data/raw/eia" \
    api uv run --locked --no-dev python -m app.ingestion.eia_contracting \
    "/data/raw/eia/downloads/$eia_filename" --table "$eia_table" --report-year 2025 \
    --retrieved-at "$eia_retrieved_at" --publication-date 2026-08-13 \
    --raw-dir /data/raw/eia --write || break
done
```

The bind mount keeps original workbook bytes on your host after one-off
containers exit. `--write` intentionally persists real EIA records. The first
import adds up to 121 observations across the four tables; if they are already
imported, it reports unchanged records. Repeating the import creates run records
but no duplicate observations. A changed value from a newer acquisition links
to the previous observation. Replaying an already successful old artifact is a
no-op. Failed parsing/import rolls back observation writes and logs a failed run.

The local implementation already downloaded and imported the reviewed 2025
workbooks. Their checksum-named originals and download manifest are under
ignored `data/raw/eia/`. Existing imports can therefore report unchanged on your
first run of the commands above. They are not bundled as application seed data:
a clean checkout needs the download/import steps, or can use the offline tests.

For local Python commands instead of Compose, configure `DATABASE_URL` for a
reachable PostgreSQL instance and add `--write --retrieved-at ...
--publication-date ... --raw-dir /absolute/private/raw` to the preview command.
These metadata flags are required for writes; they must describe the actual
acquisition and report vintage, not values copied blindly from this example.

## Worked Table 9 row

The reviewed workbook's first row is delivery year **2026**, minimum **1511**,
maximum **1511**. It belongs to **report year 2025** and represents future
purchases under contracts signed in that reporting year.

The adapter emits two facts:

```text
series_id=eia_t9_minimum, report_year=2025, delivery_year=2026,
value=1511.00000000, unit="thousand lb U3O8 equivalent"

series_id=eia_t9_maximum, report_year=2025, delivery_year=2026,
value=1511.00000000, unit="thousand lb U3O8 equivalent"
```

The contract signing/reporting year is not replaced by the delivery year.
A single generic `year` field would lose this distinction. For a published
horizon total, `delivery_year` is null and API `period_label` says
`2026–2035 total`; that row must not be mistaken for an unknown delivery year.

A cell containing `W` becomes `raw_value="W"`, `value_status="withheld"`, and
`value=null`. A blank, `--`, `NA`, or `N/A` becomes `missing` with null value.
Unknown markers, negative values, fractional contract counts, uncached formulas,
or mismatched headers fail. Withheld components are never inferred from totals.

`Decimal(str(cell.value))` avoids introducing new binary arithmetic error.
Original numeric cells and formatting remain in the retained workbook; parsed
cell text is preserved as `raw_value`, and normalized storage rounds to eight
decimal places to fit the existing database schema. Table 7 contains fractional
thousand-pound quantities even though its web table rounds to whole numbers.
Quantity/count totals are checked when all components are available, allowing
independent-rounding tolerance for quantities. Contract counts must reconcile
exactly. Weighted-average prices are not additive totals.

## Inspect typed API responses

Start/rebuild the API as above, then open http://localhost:8000/docs or run:

```bash
curl --fail 'http://localhost:8000/api/v1/contracts/signings?scope=us&report_year=2025'
curl --fail 'http://localhost:8000/api/v1/contracts/future-deliveries?scope=us&report_year=2025&table=9'
curl --fail 'http://localhost:8000/api/v1/contracts/future-deliveries?scope=us&report_year=2025&table=10'
curl --fail 'http://localhost:8000/api/v1/contracts/deliveries?scope=us&report_year=2025'
```

Responses explicitly identify U.S. geography/population. Each point carries its
metric/measure, unit, currency where relevant, reporting/delivery periods,
contract/material/supplier/bound dimensions, status, source URL/table, report
publication/revision date, vintage, retrieval time, run ID, artifact checksum,
and quality notes. Decimal `value` fields serialize as JSON strings to preserve
precision; unavailable values are null. Per-point provenance refers to the
artifact that introduced that value, not necessarily the latest check attempt.
All retrieval attempts remain in `ingestion_run`.

`scope=global`, unsupported table choices, and invalid report years return 422.
With no matching successful import, a configured database returns 200 with
`data_status="unavailable"` and empty points. Unconfigured/unreachable databases
return 503. There is no silent mock fallback. Querying multiple reporting years
returns explicitly labelled points; clients must preserve the vintage grouping.

The existing `/market/summary`, price endpoints, and frontend remain synthetic.
Milestone 7 will connect the EIA chart responses. Cameco import/display remains
pending permission, with mock prices and manual-check guidance as specified.

## Tests and validation evidence

```bash
uv run --directory backend pytest tests/test_eia_contracting.py

docker compose run --rm --no-deps -T -e RUN_POSTGRES_TESTS=1 \
  -v "$PWD/backend/tests:/app/tests:ro" \
  api uv run --locked pytest tests
```

The compact `.xlsx` fixtures under `backend/tests/fixtures/eia/` preserve EIA's
reviewed table values. `sources.json` records source links, acquisition times,
original/fixture checksums, attribution and fixture preparation. Formatting,
charts, internal workbook paths, and original document metadata were removed.
Tests mutate cells in memory for missing values, changed layouts, formula-cache
failures, bad totals, and revisions. They do not fetch live sources. Integration
tests use isolated schemas and roll them back; raw artifacts use temporary dirs.

Manual source checks: Table 8 total count 22, quantity 4321 thousand pounds,
weighted price 70.46; Table 9 2026 minimum/maximum 1511; Table 10 all-supplier
horizon maximum 174095, with later year maxima withheld; Table 7 U3O8 spot
quantity 5679.5 in workbook versus rounded 5680 on the webpage. The reviewed
public table links above support these comparisons without conflating precision.

Keep snapshots and report metadata together. Future report layouts require
review, not an automatic version bump. No older report years have been backfilled;
there is currently one 2025 vintage, not a complete annual contracting history.


Implementation verification: **84 tests passed against PostgreSQL**, with only
the previously known Starlette/HTTPX deprecation warning. The four original
workbooks were imported into the local application database: 121 facts on the
first pass, zero additions/revisions on repeat. Live HTTP checks passed for
all four table views and confirmed the old market-summary endpoint stays mock.
The API container was rebuilt and restarted with these routes; Swagger UI's
interactive controls can be reviewed manually at `/docs`.
