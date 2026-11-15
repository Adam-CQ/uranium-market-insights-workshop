# Uranium Market Dashboard

Educational market information, not investment advice. This workshop follows
[_docs/uranium_market_dashboard_spec.md](_docs/uranium_market_dashboard_spec.md).

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
There are no download/refresh commands yet. Forecasts, global contracting, and
live feeds are not part of this scaffold. See the specification for source-use
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
