# Uranium Market Dashboard

Educational market information, not investment advice. This workshop follows
[_docs/uranium_market_dashboard_spec.md](_docs/uranium_market_dashboard_spec.md).

## Current data status

The dashboard, price endpoints, and market-summary preview currently display
**invented mock data**. Dedicated EIA contracting endpoints now serve imported
2025 U.S. observations; the dashboard will connect to them in Milestone 7. We will continue using synthetic prices while permission for
Cameco import and display remains unresolved. Mock values are not expected to
match Cameco's published prices and must not be used to check actual market levels.

Milestone 5's parser and database adapter are implemented and tested with synthetic
fixtures; real-data import and source-value validation remain pending. See the
[source review](data/README.md) and [Cameco terms](https://www.cameco.com/terms-of-use).

Milestone 7 will add detailed manual-check instructions beside the price chart
and in this README, with links to [Cameco's uranium price page](https://www.cameco.com/invest/markets/uranium-price),
its methodology, and reuse terms. The guide will explain how to inspect the
published series, observation month, units, missing values, and methodology
changes. It will distinguish reviewing the source from validating our mock
prices; comparing imported values is conditional on permitted real-data use.

## Milestone 1: local scaffold

FastAPI serves HTTP requests, React renders the browser interface, and Vite
serves and builds the frontend. PostgreSQL has a persistent Compose volume;
the API does not query it until the persistence milestone. `/health` reports
API liveness only. No real market data is included yet; Milestone 2 uses synthetic fixtures.

Python dependencies live in `backend/pyproject.toml` and `backend/uv.lock`.
`uv` manages `backend/.venv`. JavaScript dependencies live in
`frontend/package.json` and `frontend/package-lock.json`; npm manages
`frontend/node_modules`. These environments communicate through HTTP.

## Run without Docker

Prerequisites: uv and Node.js 24 with npm. From the repository root:

```bash
uv sync --directory backend --locked
uv run --directory backend uvicorn app.main:app --reload --port 8000
```

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

Open http://localhost:5173 and click **Check API connection**. Expected:
“API is healthy”. API documentation is at http://localhost:8000/docs.
`--reload` restarts the API after edits; `--strictPort` fails rather than
silently choosing another frontend port.

## Run with Docker Compose

In WSL2, start Docker Desktop and enable integration for this Ubuntu distro
under Settings → Resources → WSL Integration. Confirm `docker compose version`
and `docker info` work before continuing.

From the repository root, set a local database password without editing `.env`:

```bash
read -rsp 'Local database password: ' POSTGRES_PASSWORD
export POSTGRES_PASSWORD
printf '\n'
docker compose up --build -d
curl --fail http://localhost:8000/health
docker compose logs --tail=50 api frontend db
```

`--build` builds the application images; `-d` runs services in the background.
Expected health response: `{"status":"ok"}`. Open http://localhost:5173 and
check the connection. Stop the stack with `docker compose down`; the database
volume remains available for the next startup.

The database port is internal. The API and frontend publish ports only on
localhost. Compose requires the password variable even for configuration
validation; do not commit passwords.

## Request walkthrough

1. React's button calls `fetch("/health")` on the frontend origin, port 5173.
2. Vite forwards that path to the API. Locally its target is `127.0.0.1:8000`;
   inside Compose, `API_PROXY_TARGET` sets it to `http://api:8000`.
3. Compose DNS resolves the service name `api` inside its network. The browser
   uses localhost and never needs to resolve that internal name.
4. FastAPI's `health()` handler returns a dictionary, serialized as JSON.
5. React checks the response and displays a status message.

Containers are running instances of images. Dockerfiles build the application
images; Compose configures ports, service names, environment variables, startup
dependencies, and the database volume. The PostgreSQL health check gates API
startup; it does not mean the API has established a database connection.

## Checks

From the repository root:

```bash
uv run --directory backend pytest
npm --prefix frontend run build
git diff --check
```

The API test verifies HTTP status and JSON using an in-process client with no
network dependency. The frontend build checks TypeScript and produces `dist/`.
Run `docker compose config --quiet` to validate Compose after setting the password.

Initial verification: API test and frontend production build are checked locally.
Compose startup/shutdown and browser rendering require manual confirmation;
Docker Desktop WSL integration was unavailable in the implementation environment.
The current Starlette version emits a deprecation warning for its HTTPX test
client integration; the test remains functional with the approved HTTPX dependency.

## Source and scope roadmap

Later milestones add [Cameco prices](https://www.cameco.com/invest/markets/uranium-price)
and [EIA U.S. utility contracting](https://www.eia.gov/uranium/marketing/index.php),
with provenance, source dates, units, freshness, and source-specific parser tests.
The [EIA workflow](data/eia.md) documents download and refresh commands. Cameco
reuse remains pending permission. Forecasts, global contracting, and live feeds
are not part of this scaffold. See the specification for source-use
requirements and the milestone sequence.

## Milestone 2: mock React dashboard

All values are invented teaching examples, not Cameco/EIA data. The snapshot
shows spot and long-term indicators, a U.S. signing count, and explicitly
unavailable source freshness. A shared range selector updates both the chart
and accessible table and recalculates price changes from the first selected
month to the latest month. Signing counts retain their separate annual period.

### Code map and worked example

- `frontend/src/mockMarket.ts`: the `UraniumPricePoint` interface, synthetic
  records, and range selection. TypeScript checks each record at build time.
- `frontend/src/Dashboard.tsx`: `Dashboard` owns range state, passes selected
  points to `PriceChart`, and supplies text props to reusable `SnapshotCard`s.
- `frontend/src/main.tsx`: mounts React and retains the API connection check.
- `frontend/src/style.css`: four/two/one-column cards at desktop/tablet/mobile
  widths, a scalable SVG, and a horizontally scrollable data table.
- `frontend/src/Dashboard.test.tsx`: Vitest/React Testing Library checks for
  mock labels, units, U.S. scope, freshness, and changing/restoring the range.

For example, the page's data flow is:

```tsx
const [range, setRange] = useState<PriceRange>("all");
const points = selectPrices(mockPrices, range);
// The select calls setRange; React renders again with the new points.
<PriceChart points={points} />
```

`points` is a prop: input passed from parent to child. `range` is state:
React remembers it and rerenders when it changes. In `mockMarket.ts`, each
record must contain `month`, `spot`, and `longTerm`; renaming `longTerm` to
`longterm` produces a TypeScript build error. Mock data lets us verify this
component flow before introducing HTTP market endpoints and ingestion.

### Run and verify

From the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run dev -- --port 5173 --strictPort
```

`ci` installs locked dependencies; `test` runs Vitest once using jsdom (a DOM
simulation); `build` checks types and bundles the app. The dashboard renders
without the API, though the connection-check button still requires it.
If using Compose, rebuild the frontend with `docker compose up --build -d`.

Open http://localhost:5173. Review at desktop and 375px mobile widths. Confirm:
all values are labelled mock; no source retrieval is claimed; switching from
all six months to the last three leaves April–June in both chart and table;
spot change becomes +2.00 USD/lb U3O8; restoring the range restores six rows.
Check that the API connection button still works when the API is running.

The chart is a simple SVG placeholder with a fixed 0–100 scale appropriate to
this fixture. ECharts integration and real source values come later. Automated
DOM tests do not verify browser layout; responsive visual review is manual.
Pause for the milestone review before proceeding to API contracts.

## Milestone 3: typed mock API contracts

Two read endpoints are available, backed by deterministic synthetic values:

- `GET /api/v1/prices/uranium?from=2025-04&to=2025-06`
- `GET /api/v1/market/summary`

The frontend still uses its local mock fixture; API integration comes later.
The API fixture matches that preview but is not an ingested dataset. Neither
endpoint claims a Cameco or EIA source. Publication/retrieval dates and source
URLs are null; provenance explicitly says `data_status: "mock"`.

### Code map

- `backend/app/schemas.py`: Pydantic models for prices, provenance, summary,
  and contracting. These define the public JSON shape and OpenAPI schemas.
- `backend/app/market_fixture.py`: synthetic values and honest source metadata;
  each call creates independent models so filtering cannot mutate later requests.
- `backend/app/api/market.py`: route handlers, calendar-month validation,
  inclusive filtering, and summary assembly.
- `backend/app/main.py`: registers the router and preserves `/health`.
- `backend/tests/test_market.py`: deterministic range, metadata, summary, and
  generated-documentation checks with no external source requests.

### Worked request and response

Start the backend from the repository root:

```bash
uv run --directory backend uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
curl --fail 'http://localhost:8000/api/v1/prices/uranium?from=2025-04&to=2025-06'
curl --fail http://localhost:8000/api/v1/market/summary
uv run --directory backend pytest
```

Quotes keep Bash from interpreting `&` as a background command. `--fail` makes
curl report unsuccessful HTTP responses. No dependency installation is needed
beyond Milestone 1. If running containers, rebuild the API after these changes.

Open http://localhost:8000/docs and expand the price route. Use **Try it out**
with `from=2025-04` and `to=2025-06`. Expect HTTP 200 and three points in each
of two series. An abbreviated response (metadata is shortened here) is:

```json
{
  "from_month": "2025-04",
  "to_month": "2025-06",
  "series": [
    {
      "series_id": "uranium_spot",
      "unit": "USD/lb U3O8",
      "currency": "USD",
      "points": [
        {"observation_month": "2025-04", "value": 74.0},
        {"observation_month": "2025-05", "value": 71.0},
        {"observation_month": "2025-06", "value": 76.0}
      ]
    }
  ]
}
```

The complete response also contains the long-term series, per-series provenance,
labels, measure types, and a synthetic-data disclaimer. React can later consume
this JSON with `fetch`, check `response.ok`, and pass `series[].points` into chart
components. Network JSON will require runtime checking or a generated client;
TypeScript interfaces alone do not validate a server response.

For example, the route declares:

```python
@router.get("/prices/uranium", response_model=PriceHistory)
```

FastAPI binds query strings to handler arguments (the external name `from`
maps to Python's `from_month`, since `from` is a Python keyword). The handler
filters fixture points and returns a `PriceHistory`. Pydantic validates fields;
FastAPI serializes the model as JSON and documents it in OpenAPI. Response-model
validation catches server mistakes; invalid client queries receive HTTP 422.

### Range behavior and verification

- Bounds are optional and inclusive; absent bounds mean the available history.
- `from=2025-03&to=2025-03` returns March only.
- `from=2030-01` returns HTTP 200 with two empty point arrays and intact metadata.
- Malformed months, year zero, and reversed ranges return HTTP 422 with `detail`.
- Summary dates reflect the latest fixture observation per metric: June 2025
  prices and reporting year 2024 U.S. signed-contract count. It does not invent
  delivery dates, source retrieval times, or a shared publication date.

Verification: all 16 backend tests pass (including the original health test).
Live local HTTP checks pass for health, Swagger UI, OpenAPI, summary, valid and
empty price ranges, and a reversed-range 422 response. The existing Starlette
HTTPX deprecation warning remains; no additional dependency was introduced.
Swagger UI's interactive browser controls still require manual review.

Review checkpoint: trace query → validation → fixture filter → Pydantic model →
JSON, then inspect the provenance and separate reporting periods in `/docs`.
Pause here before adding PostgreSQL schema and migrations in Milestone 4.

## Milestone 4: PostgreSQL schema and provenance

SQLAlchemy describes tables and queries in Python; psycopg transports SQL to
PostgreSQL; Alembic applies numbered schema migrations. All three are pinned in
the uv manifest/lockfile. No `.env` changes are required. The API still serves
the Milestone 3 synthetic responses; persistence is a foundation for ingestion.

### Code map and relationships

- `backend/app/db/schema.py`: four SQLAlchemy table definitions and constraints.
- `backend/app/db/connection.py`: explicit database-command configuration; importing
  the API does not connect to a database or require a password.
- `backend/migrations/versions/0001_provenance.py`: frozen initial schema migration.
- `backend/migrations/env.py`, `backend/alembic.ini`: Alembic execution configuration.
- `backend/app/db/demo.py`: synthetic insert/query/duplicate demonstration.
- `backend/tests/test_database.py`: opt-in real PostgreSQL migration and constraint tests.
- `backend/tests/test_migration_sql.py`: offline PostgreSQL SQL compilation test.
- `backend/Dockerfile`, `compose.yaml`: include migration files and pass internal
  database connection settings to the API container.

`data_source` has many `metric_definition` and `ingestion_run` rows. Each
`market_observation` refers to a metric and ingestion artifact. Primary keys
identify rows; foreign keys enforce relationships. Composite foreign keys stop
an observation from pairing one publisher's metric with another's source file.

Metric definitions carry unit, currency, geography, population, measure type,
and methodology. Treat existing definitions as immutable when importing data;
create a new series definition if its meaning changes. Runs carry the actual
source URL/table, vintage, optional publication date, retrieval time, file
identifier, SHA-256 checksum, method version, execution status, and notes.
Repeated attempts may have different run IDs; they do not create duplicate facts.

Observations preserve raw text plus `NUMERIC(24,8)` normalized values, status,
quality notes, and separate observation date, reporting year, and delivery year.
`W` (withheld) and missing values require null normalized values, never zero.
An available value must have a nonnegative normalized value. Contract type and
scenario are separate dimensions. Subdivided material/product categories should
use distinct metric definitions when later table adapters require them.

The unique fact key includes metric, artifact checksum, all period fields,
contract type, and scenario. `NULLS NOT DISTINCT` prevents optional null fields
from allowing duplicates (PostgreSQL 15+, matching our PostgreSQL 18 service).
A changed artifact checksum permits another vintage of the fact; link it with
`supersedes_observation_id` and retain the original. The database enforces a
same-metric revision link; future importers must also verify matching periods
and dimensions and avoid revision cycles. The schema does not itself implement
provider parsing, automatic revision detection, or raw artifact storage.

### Run migrations with Compose

Start Docker Desktop and enable Ubuntu WSL integration first. From the project
root, set the same password used when creating the existing database volume:

```bash
read -rsp 'Existing local database password: ' POSTGRES_PASSWORD
export POSTGRES_PASSWORD
printf '\n'
docker compose up --build -d db api
docker compose exec api uv run --locked --no-dev alembic upgrade head
docker compose exec api uv run --locked --no-dev alembic current
docker compose exec api uv run --locked --no-dev python -m app.db.demo
```

`upgrade head` applies pending migrations; running it again does nothing when
already current. `current` should show `0001_provenance (head)`. The demo prints
one mock price record and confirms that a repeat insert reused its observation.
It rolls back all demo writes, including source, metric, run, and observation
rows. No actual Cameco data is downloaded. Do not change the password to an
existing volume: PostgreSQL initialization variables do not reset its password.

On a clean database, the same upgrade creates all four tables plus Alembic's
version table. Do not remove your existing volume to simulate a clean database;
the integration suite uses a new isolated schema instead.

### Worked observation trace

The executable demo generates raw text `76.00` and its fixture checksum. The
source identifies an explicitly synthetic publisher; the metric defines mock
spot prices in USD/lb U3O8. The run ties that checksum to `workshop-mock-v1` and
`demo-v1`. The observation stores June 30, 2025, raw `76.00`, exact decimal
`76.00000000`, and `data_status='mock'`.

Its join is conceptually:

```sql
SELECT s.name, m.series_id, m.unit, o.observation_date,
       o.raw_value, o.normalized_value, r.source_vintage
FROM market_observation AS o
JOIN metric_definition AS m ON m.id = o.metric_id
JOIN data_source AS s ON s.id = m.source_id
JOIN ingestion_run AS r ON r.id = o.ingestion_run_id;
```

The future price response mapping is `observation_date` → `observation_month`
(`2025-06`), `normalized_value` → `value`, metric unit/currency → series metadata,
and joined source/run fields → provenance. The current API fixture still
supplies that response independently; the demo is not a database-backed API.

### Verify

Run the non-database suite locally:

```bash
uv sync --directory backend --locked
uv run --directory backend pytest
```

Run real PostgreSQL checks through Compose, keeping the database port internal:

```bash
docker compose run --rm -e RUN_POSTGRES_TESTS=1 \
  -v "$PWD/backend/tests:/app/tests:ro" \
  api uv run --locked pytest tests
```

This one-off container installs the already locked test dependencies. The tests
create a randomly named schema, apply the migration, compare it with the Python
models, insert/query fixtures, reject duplicates and invalid foreign keys,
check suppression, and preserve a revised value beside the original. Each
schema and its data are rolled back. The database user needs permission to
create schemas. Expected with PostgreSQL available: **30 passed**.

Alternatively, for an existing locally reachable PostgreSQL test database, set
`TEST_DATABASE_URL` to a `postgresql+psycopg://...` URL and run the local pytest
command. Tests use isolated schemas, not existing application tables. Local
migration/demo commands accept `DATABASE_URL`; Compose supplies `DB_HOST=db`
and `POSTGRES_PASSWORD` instead. Connection URLs containing special characters
must be URL-encoded; the password-based configuration handles escaping itself.

Implementation verification: **17 passed, 13 PostgreSQL tests skipped** because
Docker/WSL integration was unavailable. The offline migration compiles to
PostgreSQL SQL; actual clean-database application and constraints remain pending
until the integration command above runs. The known HTTPX warning remains.
Review these results before proceeding to source ingestion in Milestone 5.

## Milestone 5: Cameco-shaped HTML adapter

See [data/README.md](data/README.md) for the source review, permission finding,
worked normalization example, synthetic import commands, and refresh procedure.
Cameco's stated terms do not establish permission for this application's data
reuse; real ingestion and redistribution remain pending written permission.
The adapter therefore makes no network requests and ships only invented data.
No new dependencies were added, and the API/frontend keep their mock fixtures.

### Code map and lesson

- `backend/app/ingestion/cameco_prices.py`: strict standard-library HTML parser,
  typed normalized observations, and an explicit file-based CLI.
- `backend/app/ingestion/price_repository.py`: raw artifact retention, source and
  metric definitions, ingestion runs, atomic writes, and revision handling.
- `backend/tests/fixtures/cameco_prices_synthetic.html`: invented dates/values and
  minimal table markup, exercising missing history, method boundaries, duplicates.
- `backend/tests/test_cameco_prices.py`, `test_cameco_database.py`: offline parsing
  and real PostgreSQL idempotence/revision/failure checks.
- `backend/tests/conftest.py`: the existing isolated-schema fixture, now shared
  between schema and ingestion tests; all integration writes roll back.

An adapter is the boundary between a provider-specific layout and our model.
`parse_prices(html)` has no network or database side effects. It returns typed
records using `Decimal` rather than binary floating-point values. The repository
then attaches source metadata and persists them. This separation lets tests
check a known fixture without relying on a changing external website.

For example, the core conversion in the parser is:

```python
month = source_date.replace(day=1)
value = Decimal(raw_value)
```

The first line identifies a month, not an actual sale date. The original source
date survives in notes and raw HTML. Blank historical long-term cells become
`None`, not `Decimal('0')`. The importer compares normalized values, skips
unchanged facts, and inserts revised values with `supersedes_observation_id`.
Raw HTML SHA-256 identifies a source artifact; it does not prove a publisher's
publication date or that reuse is licensed.

### Commands and review checkpoint

```bash
uv run --directory backend python -m app.ingestion.cameco_prices \
  tests/fixtures/cameco_prices_synthetic.html --synthetic
uv run --directory backend pytest
```

The first command previews 8 mock observations and a duplicate warning without
writing files or connecting to PostgreSQL. The local suite skips integration
checks unless a database is configured. The full Compose test command is in
`data/README.md`; it includes parser and database checks, not live network calls.

Verification on 2026-11-15: 56 tests passed with real PostgreSQL, including the
Milestone 4 migration/constraint checks previously pending WSL integration.
The source-page review confirmed the HTML column structure, mixed date labels,
and identical duplicate-month case. Actual price data was not imported or
included in fixtures. Live source-value validation remains pending permission.
Pause for review before EIA ingestion; source licensing remains an open MVP item.


## Milestone 6: EIA workbook ingestion and contracting API

The importer reads official EIA `.xlsx` Tables 7, 8, 9, and 10. `openpyxl` is pinned
in the uv-managed backend. The report-year/delivery-year distinction, material,
contract type, supplier scope, minimum/maximum bounds, units, and withheld/missing
values remain explicit. No database migration was needed: each material/supplier/
bound combination has a distinct metric definition in the existing schema.

**Table 8 qualification:** its signing count covers contracts signed in the
reporting year with deliveries received that year. It is not every contract
signed regardless of first delivery. Table 7 quantities are deliveries with
reported price. See [data/eia.md](data/eia.md) for definitions and attribution.

### Code map and concept lesson

- `backend/app/ingestion/eia_contracting.py`: workbook adapter, numeric/marker
  normalization, definition and totals checks, preview/import CLI.
- `backend/app/ingestion/eia_repository.py`: checksum-named raw retention,
  provenance, idempotent atomic imports, revisions, and failure-run logging.
- `backend/app/api/contracts.py`: typed PostgreSQL read endpoints with U.S.-only
  scope, period/dimension labels, units, source metadata, and availability status.
- `backend/tests/fixtures/eia/`: compact permitted EIA source-value workbooks and
  attribution/checksum manifest; no live network dependencies in tests.
- `backend/tests/test_eia_contracting.py`, `test_eia_database.py`: parser and
  database/API behavior, including withheld/missing values and repeat imports.

A workbook is a set of sheets and cells, with headers, footnotes, merged cells,
and sometimes formulas or charts. The adapter validates the reviewed sheet and
headers before interpreting cells; it does not treat the whole workbook as one
flat CSV. `W` means withheld, not a numeric zero. Quantities and weighted-average
prices are separate metrics, so a price column cannot become a contracting bar.

Worked example: a Table 9 row for delivery year 2026 has `report_year=2025` and
`delivery_year=2026`; minimum and maximum become separate quantity metrics in
thousand pounds U3O8 equivalent. Both periods survive through the database and
JSON response. A Table 7 delivery in 2025 instead has delivery/report year 2025;
it must not be combined with that forward contracted quantity as one series.

### Commands and review checkpoint

Follow [the EIA download/import guide](data/eia.md) for exact commands, metadata,
expected results, source comparisons, and how to inspect `/docs`. To run tests:

```bash
uv sync --directory backend --locked
uv run --directory backend pytest tests/test_eia_contracting.py

docker compose up --build -d db api
docker compose run --rm --no-deps -T -e RUN_POSTGRES_TESTS=1 \
  -v "$PWD/backend/tests:/app/tests:ro" \
  api uv run --locked pytest tests
```

Read endpoints are `/api/v1/contracts/signings`, `/future-deliveries` (choose
`table=9` or `table=10`), and `/deliveries`, all under `/api/v1/contracts` with
`scope=us` and optional `report_year=2025`. They return available EIA imports;
they do not silently substitute mock data when a source is unavailable.

Verification: **84 backend tests passed against PostgreSQL**. The four official
2025 workbooks imported 121 facts; repeating the import added no duplicates.
Live HTTP checks passed for all four EIA table views, and the market summary
retained its mock status. The known Starlette/HTTPX warning remains.

The dashboard and existing price/market-summary endpoints remain mocked, as
agreed. Cameco permission is still unresolved; EIA's public reuse policy permits
these survey-data imports with attribution. Stop at this review checkpoint
before chart integration and manual source-check guidance in Milestone 7.
