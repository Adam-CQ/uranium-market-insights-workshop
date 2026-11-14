# Uranium Market Dashboard — Product Specification

**Status:** Working specification for Phase 1; ready for review before implementation.

## 1. Product decision and vision

Phase 1 is focused on **uranium market context**. The application is an educational market dashboard that helps a user understand uranium prices, utility contracting, and the broader supply-and-demand context. It is not initially a stock screener, company valuation tool, or trading recommendation system.

The dashboard should make it possible to answer:

1. How have the published uranium spot and long-term price indicators changed over time?
2. What do publicly reported contracting figures tell us, and what population do they cover?
3. How do published uranium supply/demand forecasts and nuclear-capacity scenarios frame possible future market conditions?
4. What are the definitions, source dates, limitations, and uncertainty behind each displayed value?

The uranium-market scope is decided for Phase 1. Individual company monitoring or valuation may be considered in a later phase and is out of scope here.

## 2. Product principles

- Education and traceability are core product features, not optional help text.
- Every metric must show its unit, period, source, publication/observation date, and geographic scope where applicable.
- Observed data, third-party estimates, and scenario projections must be visibly distinguishable.
- Values with different scopes or definitions must not be overlaid as if they were directly comparable.
- Do not imply real-time uranium-market data. The uranium market is privately negotiated and the selected price series are published periodically.
- Do not bypass paywalls, authentication, robots restrictions, or provider terms. Prefer official downloadable tables and documented public pages.

## 3. MVP dashboard and visualizations

### 3.1 Market snapshot cards

Show a small top row with:

- Latest Cameco-reported spot-price indicator, with its observation date and change over a selected period.
- Latest Cameco-reported long-term price indicator, with its observation date and change over a selected period.
- Latest available utility contracting measure, with an explicit label such as “U.S. reactor owners/operators — EIA”.
- Data freshness status, showing when the source was published or last retrieved.

Cards must show different update frequencies honestly; do not imply that all values update together.

### 3.2 Uranium price history

Use a time-series line chart for Cameco's spot and long-term price series.

- Plot the two indicators as separate series on the same price scale and unit.
- Provide a selectable time range.
- Identify the currency and unit exactly as provided by the source (expected USD per pound U3O8; confirm against the current source when ingesting).
- Show the last observation date and source methodology beside the chart.
- Explain that these are published market indicators, not transaction prices for every uranium sale.

### 3.3 Contracting activity

Use annual bars or a compact annual time-series view for newly signed contracts. Keep these measures separate:

1. Contracts signed during a reporting year.
2. Future delivery quantities associated with contracts signed during that year, grouped by delivery year.
3. Deliveries made during a reporting year, classified by contract type where available.
4. Maximum future deliveries under contracts already in effect (if included).

The MVP's reproducible contracting series is EIA data covering U.S. civilian reactor owners/operators. Mark the geography and population in the chart title/subtitle and metadata. Do not combine it with global UxC estimates into one continuous series.

Global figures disclosed by Cameco and attributed to UxC may be included as a separate, manually curated reference/validation view. Each observation must carry the report date, source link, and “global estimate reported by Cameco, citing UxC” label. Do not interpolate missing years or imply this is a complete open global dataset.

### 3.4 Supply-demand outlook (follow-on visualization)

When a suitable source dataset and permitted use are established, compare projected uranium requirements and projected supply over time. Show scenario name, report vintage, units, and supply components where available. Separate historical observations from forecasts. Explain that a projected supply gap is scenario-dependent and is not proof of a physical shortage.

### 3.5 Nuclear capacity context (follow-on visualization)

Show published nuclear-capacity projections as a separate chart, not as a uranium-demand series. Preserve the publisher's capacity categories (e.g., operating, under construction, planned, proposed, potential, or target additions) and explain their differing certainty.

### 3.6 Education content

Include a “How to read this dashboard” section and a glossary. At minimum explain:

- Spot price indicator versus an actual transaction price.
- Long-term price indicator and the fact that uranium contracts are privately negotiated.
- Contract signing year versus delivery year versus actual delivery.
- EIA's U.S. reactor-owner/operator scope versus global market estimates.
- Supply gap as a forecast/scenario, not an observed shortage.
- Nuclear capacity as a demand driver/context measure, not a direct uranium-demand measure.
- Source date, observation period, unit, revisions, and data freshness.

## 4. Data sources and ingestion requirements

### 4.1 Cameco uranium prices — MVP price source

- Public page: [Cameco — Uranium Price](https://www.cameco.com/invest/markets/uranium-price)
- Market overview: [Cameco — Markets](https://www.cameco.com/invest/markets)
- Cameco explains that uranium is not traded on an open market like many commodities and that its industry-average prices use month-end prices published by UxC and TradeTech. Long-term price history before May 2004 is based on TradeTech only.
- The public page presents historical spot and long-term observations. Treat the webpage as the public source unless Cameco documents a supported download/API endpoint. Do not assume an undocumented API is stable.
- Ingestion cadence: monthly/periodic refresh, checked manually or by a conservative scheduled job. Store retrieval time separately from the source observation date.
- Preserve source value, normalized value, date, currency, unit, source URL, retrieval timestamp, and method/version. Detect revisions rather than silently overwriting historical source data.
- Verify the page's terms and permitted reuse before public deployment; attribute Cameco and do not redistribute restricted underlying UxC/TradeTech data beyond what Cameco makes publicly available.

### 4.2 EIA Uranium Marketing Annual Report — MVP contracting source

- Report landing page: [EIA — Uranium Marketing Annual Report](https://www.eia.gov/uranium/marketing/index.php)
- Table 8, contracts signed in reporting year: [EIA Table 8](https://www.eia.gov/uranium/marketing/table8.php) (PDF/XLS links are provided from the report page).
- Table 9, contracts signed in the reporting year grouped by future delivery year: [EIA Table 9](https://www.eia.gov/uranium/marketing/table9.php) (confirm current link and available formats on the report page when implementing).
- Table 10, deliveries under contracts in effect at year-end by future delivery year: [EIA Table 10](https://www.eia.gov/uranium/marketing/table10.php).
- Table 7, delivered uranium by contract type and delivery year: access via the report landing page; select the table labelled “by contract type and delivery year”.
- EIA publishes XLS and PDF formats. Prefer the official XLS tables for ingestion; retain the original workbook and report vintage in the raw-data area.
- Scope: owners/operators of U.S. civilian nuclear power reactors (COOs), not global utility contracting.
- EIA distinguishes spot contracts (typically one-time delivery, usually within a year of execution) from long-term contracts (one or more deliveries at least a year after execution). Preserve EIA's definitions and do not substitute our own silently.
- Cadence: annual. The latest report may be revised; retain the report year, publication/revision date, retrieval timestamp, source table, and source file checksum.

### 4.3 Global contracting reference points — not a complete MVP time series

- Cameco investor reports and regulatory filings: [Cameco quarterly and annual reports](https://www.cameco.com/invest/financial-information/quarterly-reports) and [Cameco annual reports](https://www.cameco.com/invest/financial-information/annual-reports).
- These reports may publish global annual spot/term contracting figures attributed to UxC. Record only figures explicitly stated in a cited report, along with year, measure definition, publication date, unit, exact report URL, and source attribution.
- UxC product information: [UxC — Ux Weekly](https://www.uxc.com/p/product/periodical/uxw) describes spot and term contracting data but is subscription-based; [UxC — Data Services](https://www.uxc.com/p/data/data-services) explains that its detailed transaction database is confidential.
- Do not scrape subscriber-only content or reconstruct confidential transaction data. A licensed UxC dataset can be considered later if the project obtains permission and budget.

### 4.4 Nuclear capacity context — follow-on source

- [World Nuclear Association — Global outlook for nuclear capacity goals](https://world-nuclear.org/our-association/publications/world-nuclear-outlook-report/global-outlook-for-nuclear-capacity-goals)
- The report's projection depends on assumptions about continued operation and the completion of reactors at different development stages and national targets. Capture the report edition/vintage and scenario assumptions.
- Prefer data files explicitly offered by the publisher. If only a chart/PDF is public, do not present values digitized from a figure as official raw data without clearly labelling them as digitized estimates and documenting the method. This visualization is follow-on scope, not a blocker for the MVP.

### 4.5 Supply-demand scenarios — follow-on source selection

- Cameco market materials and World Nuclear Association publications can inform the initial research, but confirm the exact underlying dataset, definition, publication vintage, and reuse rights before building an ingest pipeline.
- UxC/TradeTech scenario data may be proprietary. Do not treat chart screenshots or third-party reproductions as unrestricted source datasets.
- Until a suitable source is verified, the application must omit the projection chart or show a clearly labelled static explanatory example—not fabricate a time series.

## 5. Data model and provenance minimum

Every ingested observation must be traceable. Use fields equivalent to:

- `series_id` / metric name;
- `observation_date` or reporting year;
- `value` and `unit`;
- `currency`, where relevant;
- `geography` and covered population;
- `measure_type` (indicator, signed contracts, contracted future deliveries, actual deliveries, forecast, capacity scenario, etc.);
- `contract_type` / `scenario` where relevant;
- `source_name`, `source_url`, `source_table` or source document;
- `source_publication_date` and `source_vintage`;
- `retrieved_at`, `ingestion_run_id`, and checksum/file identifier;
- `data_status` (observed, estimate, forecast, digitized estimate, revised);
- `methodology_notes` and quality/revision notes.

Never collapse signing year and delivery year into one date field. Never combine differently scoped series without explicit transformation and labelling.

## 6. Recommended technology stack

Use this as the Phase 1 implementation baseline. Keep versions pinned in project manifests/lockfiles when implementation begins; do not copy historical patch versions from older project documents without rechecking compatibility.

| Layer | Technology | Phase 1 responsibility |
|---|---|---|
| Frontend | React + TypeScript + Vite | Dashboard pages, chart interactions, source/freshness labels, educational explanations |
| Charts | Apache ECharts (React integration) | Responsive time-series, annual bars, forecast/scenario charts, tooltips and annotations |
| Backend API | Python + FastAPI + Pydantic | Typed API, validation, query endpoints, health checks, ingestion status |
| Relational database | PostgreSQL | Normalized observations, provenance, source metadata, ingestion runs, definitions |
| Analytical files | Parquet | Durable local analytical snapshots and reproducible raw/normalized extracts |
| Local analytical engine | DuckDB | SQL exploration and analysis over Parquet; include a small educational example in `tests/` or `examples/` |
| Local environment | Docker Compose | Run frontend, API, PostgreSQL, and supporting services locally |
| Tests | pytest for Python; Vitest/React Testing Library for frontend | Unit and API behavior, parsing/normalization, chart-data contracts |

### Explicitly deferred

- **Redis + Celery:** teach and introduce as a later bounded workshop step for scheduled/background ingestion if the synchronous/simple scheduled MVP needs it. Do not require it to render initial historical data.
- **WebSockets:** keep a small educational example in an `examples/` or `tests/` area, but do not use WebSockets for monthly Cameco price updates or annual EIA data. The example should demonstrate connection, server push, client receipt, and disconnect/reconnect behavior with mock data.
- **AWS deployment:** design the app to be container-friendly and cloud-portable, but Phase 1 must run locally first. AWS deployment is a later milestone; avoid adding AWS-only dependencies to the core data model.
- **LLM sentiment:** not part of this uranium-market-context MVP. Reassess only after the core sources, provenance, and user value are established.

## 7. Suggested repository structure

```text
uranium-market-dashboard/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── ingestion/
│   │       ├── cameco_prices.py
│   │       └── eia_contracting.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── charts/
│   │   ├── pages/
│   │   └── education/
│   └── package.json
├── data/
│   ├── raw/                 # source files, only where reuse permits
│   ├── processed/           # normalized Parquet snapshots
│   └── README.md            # provenance, licensing, refresh instructions
├── examples/
│   ├── duckdb_parquet_demo/
│   └── websocket_demo/
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   └── data-model.md
├── docker-compose.yml
└── README.md
```

Do not commit licensed or restricted source data. Store only permitted public source extracts, or provide commands/instructions for users to download them themselves.

## 8. API outline for MVP

Suggested read endpoints:

- `GET /api/v1/market/summary` — latest available price indicators, latest contracting year, and freshness metadata.
- `GET /api/v1/prices/uranium?from=YYYY-MM&to=YYYY-MM` — Cameco spot and long-term series.
- `GET /api/v1/contracts/signings?scope=us` — EIA new contract signings by reporting year.
- `GET /api/v1/contracts/future-deliveries?scope=us&report_year=YYYY` — contract quantities by delivery year, where available.
- `GET /api/v1/contracts/deliveries?scope=us` — actual deliveries by year/type, where available.
- `GET /api/v1/sources` — source definitions, links, cadence, scope, last retrieval, and caveats.
- `GET /health` — service health.

Do not expose a global contracting time series endpoint until data coverage and licensing support it. Return units, scope, as-of date, source, and status alongside chart values.

## 9. Non-functional requirements

- App starts locally from documented commands and a clean checkout.
- No source API key is required for MVP public pages/files.
- Ingestion is idempotent: repeated import of the same source vintage does not duplicate observations.
- Ingestion logs failures and source revisions; the dashboard shows unavailable/stale data clearly.
- Calculations and parsers have deterministic tests using small fixtures, not live network dependencies.
- Raw source artifacts and normalized records remain distinguishable.
- Chart responses are documented and validate against typed schemas.
- Provide an accessible textual explanation/table alternative for chart data.
- Clearly label the application as educational market information, not investment advice.

## 10. Definition of done for Phase 1

Phase 1 is complete when:

1. A developer can start the app locally using the README instructions and Docker Compose.
2. The dashboard displays Cameco's public historical spot and long-term price observations with source and date metadata.
3. The dashboard displays EIA contracting/signing data with the U.S.-only scope clearly visible and signing/delivery concepts kept separate.
4. The source/freshness details and plain-language explanations are accessible from the relevant charts.
5. At least one ingestion/parser test per MVP source passes without depending on a live external service.
6. A DuckDB + Parquet educational example demonstrates reading an included or user-downloaded permitted dataset.
7. A WebSocket educational example demonstrates basic message flow using mock data, without implying that uranium market data is streamed in real time.
8. The README documents source links, download/refresh steps, data limitations, and how to run tests.

## 11. Agent implementation guidance

This is a **bootcamp/workshop project** as well as a software deliverable. The goal is a working local application and for the developer to understand how its parts fit together. Do not generate the entire application in one pass or skip directly to a polished UI.

### Required teaching format for every milestone

Before changing code, the agent must provide:

1. **Goal:** the user-visible or engineering outcome of this bounded milestone.
2. **Concept lesson:** explain the relevant technology and why it is being used here, at a practical level.
3. **Code map:** name the files/modules to be created or changed and explain their responsibilities and dependencies.
4. **Small worked example:** show a short, relevant code example (or walk through the implementation line by line) and connect it to the running application. Examples should be executable where practical, not abstract textbook snippets.
5. **Commands:** give exact commands to install/run/test the milestone, explaining important flags and expected output.
6. **Verification:** run the checks, show what passed/failed, and explain what the result demonstrates.
7. **Review checkpoint:** summarize what the developer should now understand and pause for the user's review before starting the next milestone.

Avoid unexplained code dumps. Introduce one new concept at a time, preserve earlier working behavior, and explain errors in context. If the user asks follow-up questions, answer them before proceeding. The user prefers one question at a time.

### Milestone sequence and teaching content

#### Milestone 1 — Project scaffold and local services

- Build the minimal repository, Docker Compose file, FastAPI health endpoint, React/Vite frontend shell, and PostgreSQL service.
- Teach: client/server responsibilities; HTTP request/response; what a frontend build tool does; containers, images, ports, environment variables, and service names in Compose.
- Worked example: trace a browser request to `/health` and explain how the frontend container/service can reach the API by Compose service name while a developer reaches it through a published localhost port.
- Verify: bring up/down the stack; open the health endpoint and frontend; check service logs; run a trivial API test.

#### Milestone 2 — React + TypeScript dashboard with mock data

- Create the first market snapshot and placeholder chart using local, explicitly labelled mock data; no live ingestion yet.
- Teach: React component tree, props, state, TypeScript interfaces, and why mock data lets UI work proceed before provider ingestion exists.
- Worked example: define a `UraniumPricePoint` type and pass a small array from a page component into a price-chart component. Explain how the type catches a misspelled or missing field.
- Verify: render the page, inspect a responsive layout, and run frontend tests for displayed labels and units.

#### Milestone 3 — API contract and FastAPI

- Implement typed read endpoints for summary and price-series responses, initially backed by a small deterministic fixture.
- Teach: route handlers, Pydantic request/response models, HTTP status codes, serialization, and API documentation.
- Worked example: follow `GET /api/v1/prices/uranium` from query parameters through response validation to JSON consumed by React; show a sample request and response.
- Verify: use FastAPI `/docs`, call the endpoint with curl or the browser, and test valid, empty, and invalid date ranges.

#### Milestone 4 — PostgreSQL schema and provenance

- Add migrations and normalized tables for source, series/metric definition, observations, and ingestion runs. Keep raw source values and normalized values traceable.
- Teach: primary/foreign keys, one-to-many relationships, constraints, migrations, and why provenance is modeled as data rather than buried in chart code.
- Worked example: trace one Cameco observation from a `data_source` row to its `market_observation` record and API response; explain how a unique key prevents duplicate imports.
- Verify: apply migrations on a clean database; insert/query a fixture; test duplicate handling and relationship constraints.

#### Milestone 5 — Cameco price ingestion

- Implement a conservative importer for the publicly visible historical price series after validating the current page structure and applicable reuse terms. Save a sanitized source fixture for tests. Do not rely on an undocumented endpoint without documenting the risk and fallback.
- Teach: source adapter boundary, parsing HTML/table data, date and unit normalization, idempotent upsert, source-vintage metadata, and why live-network tests are brittle.
- Worked example: show one raw row becoming a typed normalized observation, including date, USD/lb unit, source URL, and retrieval timestamp.
- Verify: parser tests against the saved fixture; explicit failure for unexpected page structure; compare a small sample against the source page.

#### Milestone 6 — EIA contracting workbook ingestion

- Implement download instructions and import for official EIA XLS tables, initially Table 8 (signed contracts), Table 9 (future delivery years for contracts signed in the report year), Table 10 (existing contracted purchases by future delivery year), and Table 7 (actual delivered uranium by contract type/material type).
- Teach: workbook/sheet parsing, `pandas` or `openpyxl` use where appropriate, reporting year versus delivery year, suppression markers such as `W`, units, rounding, and U.S.-only scope.
- Worked example: map one Table 9 row to a fact record with both `report_year` and `delivery_year`; show why using a single generic `year` column would be ambiguous. Explain why suppressed values must not be coerced to zero.
- Verify: fixture-based parser tests for normal, withheld, and missing values; confirm totals and units against the official table; ensure U.S.-only label is returned by the API.

#### Milestone 7 — Interactive visualizations and educational explanations

- Connect API responses to the price and contracting charts; add tooltips, source links, as-of labels, scope chips, and “How to read this” explanations.
- Teach: chart-data contract, time-series versus categorical chart choice, tooltip design, accessibility, and how scale/aggregation can mislead.
- Worked example: trace a plotted bar back to a Table 8 observation and its provenance, then compare it with a Table 7 delivery observation to demonstrate why they are different series.
- Verify: UI tests for title, scope, unit, date, and source; manual review that no U.S. EIA bar is visually merged with global Cameco/UxC reference figures.

#### Milestone 8 — DuckDB + Parquet learning example

- Add a small standalone example that writes or reads a permitted normalized dataset in Parquet and queries it with DuckDB. Keep PostgreSQL as the app's normalized operational store; do not imply Parquet replaces it.
- Teach: row/columnar storage contrast, Parquet files, analytical scans, DuckDB's in-process SQL engine, and when the example is useful versus a relational application database.
- Worked example: show a short SQL query such as `SELECT observation_date, spot_price FROM read_parquet('...') ORDER BY observation_date` and explain the result and file boundary.
- Verify: run the example from documented commands and compare its result with the equivalent API/database query for the same fixture.

#### Milestone 9 — WebSocket educational example (not live uranium feed)

- Create a small isolated example using mock price-like messages to demonstrate WebSocket connection, server push, client receipt, and disconnect/reconnect. Do not connect it to scraped or real-time uranium prices.
- Teach: how WebSockets differ from ordinary HTTP request/response, the persistent connection lifecycle, and when this technology is justified. Explain that the selected uranium source cadence does not warrant a WebSocket in the production dashboard.
- Worked example: run the FastAPI WebSocket route and a minimal frontend/example client; show a message such as `{"sequence": 1, "value": 100.0}` flowing from server to client.
- Verify: observe messages in the client, stop/restart the server, and explain the disconnect state. Include a test for message shape and connection behavior.

#### Milestone 10 — End-to-end review and handoff

- Confirm clean local startup, documented data refresh, frontend/backend tests, ingestion tests, explanatory content, known limitations, and no accidental licensed-data commits.
- Teach: how the complete data path fits together, how to debug a broken source-to-chart flow, and the difference between local reproducibility and production deployment.
- Worked example: trace one price point and one EIA contract fact from source through ingestion, storage, API, chart, and displayed explanation.
- Verify: follow README from a clean environment, run all checks, and record exact commands and outcomes. Only after this milestone should AWS deployment be planned as a separate phase.

Redis/Celery, advanced forecasting, continuous ingestion, and AWS deployment are later teaching/build milestones. Do not introduce them before the local MVP works and the user has reviewed the preceding milestone. At each checkpoint, wait for the user before moving forward.
