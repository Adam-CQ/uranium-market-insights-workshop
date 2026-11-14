# Uranium Market Dashboard

Educational market information, not investment advice. This workshop follows
[_docs/uranium_market_dashboard_spec.md](_docs/uranium_market_dashboard_spec.md).

## Milestone 1: local scaffold

FastAPI serves HTTP requests, React renders the browser interface, and Vite
serves and builds the frontend. PostgreSQL has a persistent Compose volume;
the API does not query it until the persistence milestone. `/health` reports
API liveness only. No market data is included yet.

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
