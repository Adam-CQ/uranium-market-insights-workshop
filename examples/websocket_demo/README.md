# Milestone 9 — Mock WebSocket lifecycle

The goal is to observe a connection, server push, client receipt, disconnect,
and reconnect using **invented, unitless price-like messages**. This is an
isolated teaching app on port 8010, not a uranium feed. It does not import any
Cameco/EIA adapters, connect to PostgreSQL, or add routes to the dashboard API.

## Concept lesson and code map

Ordinary HTTP follows a request/response pattern. Loading this client is an HTTP
request. A WebSocket then establishes one persistent bidirectional connection;
the server can send later frames without a new client request for every value.
That can be useful for chat or interactive event streams. Monthly Cameco and
annual EIA publications do not justify it in our dashboard.

- `server.py`: a separate FastAPI app, validated `MockMessage`, independent
  message producer, and `/ws/mock` route. It serves the HTML/JS client locally.
- `client.html`: controls, connection status, visible mock notice, last session/
  sequence, and a bounded message log.
- `client.js`: browser WebSocket lifecycle and explicit reconnect state. Retry
  delays are 1, 2, 4, then at most 8 seconds. Attempts continue until stopped;
  the user can cancel them with Disconnect or the reconnect checkbox.
- `check_client.mjs`: optional automated DOM check of the actual JS client using
  jsdom and real local WebSocket frames, including stopping/restarting Uvicorn.
- `backend/tests/test_examples.py`: message validation, repeated connections,
  sequence reset, disconnect cleanup, and absence of the route from the main API.

## Run from the repository root

```bash
uv sync --directory backend --extra examples
uv run --project backend --extra examples uvicorn examples.websocket_demo.server:app --host 127.0.0.1 --port 8010
```

`--project backend` uses the existing uv-managed Python environment and leaves
module lookup at the root. `--extra examples` supplies the optional WebSocket
implementation for Uvicorn. Binding to `127.0.0.1` makes this a local example.
If 8010 is occupied, select another port and open that port in the browser.
No Docker or running dashboard is required.

Open **http://127.0.0.1:8010** and click **Connect**. The page initially loads
through HTTP, then connects to `ws://127.0.0.1:8010/ws/mock`. The JS derives the
host/port from the page origin and chooses `wss:` if served over HTTPS.

## Small worked message

The server builds and validates a message before sending it:

```python
message = make_message(sequence, connection_id)
await websocket.send_json(message.model_dump(mode="json"))
```

The first JSON frame has this shape (the UUID differs each time):

```json
{
  "sequence": 1,
  "value": 100.0,
  "data_status": "mock",
  "connection_id": "12345678-1234-4234-8234-123456789abc"
}
```

The next sequence has value 100.25. Values cycle in a deterministic teaching
pattern; no market or external API is involved. `sequence` counts frames in one
connection. The UUID identifies that connection. `data_status` prevents the
example from being presented as observed uranium prices.

In the client, `onmessage` parses JSON, checks the mock label and basic shape,
then displays the payload as text. It keeps the latest 50 messages. The server's
producer pushes independently while a receive loop waits for client disconnect;
its cleanup cancels the producer so it does not keep running after the connection
closes.

## Disconnect/reconnect exercise

1. Connect and observe successive messages arriving without clicking another
   button. In browser developer tools, Network → WS shows the single connection
   and frames. The unitless values are visibly labelled mock.
2. Click **Disconnect**. Message receipt and pending retries stop. Click Connect
   again: the connection ID changes and sequence starts again at 1.
3. Leave **Automatically reconnect** checked. In the server terminal press
   **Ctrl+C**, keeping the client page open. Observe its disconnected/retrying
   status; failed attempts back off to a maximum 8-second delay.
4. Restart the same server command. The open client page reconnects automatically.
   It receives sequence 1 under a new connection ID. This is a new stream, not
   continuation or replay of frames missed during downtime.
5. Uncheck automatic reconnect and repeat the server stop. The client stays
   disconnected. Explicit Connect starts another attempt; checking reconnect
   again can resume attempts after an unexpected disconnect.

A connection succeeding does not establish message durability. This example has
no persistent event log, replay, or cross-connection sequence continuity. Keep
that distinction separate from the dashboard's durable ingestion records.

## Automated verification

```bash
uv run --directory backend --extra examples pytest tests/test_examples.py
```

The focused Python suite checks the two examples together. WebSocket tests use
FastAPI's in-process client, so they need no open port or live source. The
message contract rejects non-mock status, invalid sequence, nonfinite values,
and unexpected fields. A black-box test confirms the dashboard rejects the demo
route and retains its health endpoint.

To verify actual local network frames and the real client JS, use the existing
frontend development dependencies:

```bash
npm --prefix frontend ci
uv run --project backend --extra examples node examples/websocket_demo/check_client.mjs
```

This needs Node.js plus the already approved jsdom dependency. It chooses a free
local port, starts its own Uvicorn process, loads the actual HTML/JS in jsdom,
receives messages, disconnects, stops/restarts the server, checks automatic
reconnect and sequence reset, then stops its processes. It does not stop a
manually running demo or your dashboard. Expected: four `PASS` lines. This is a
DOM/network integration check; it does not substitute for browser visual review.

Review checkpoint: perform the browser exercise and explain the differences
between HTTP loading, server push, retry delay, and replay. Then return to the
main dashboard: its monthly/annual source updates continue to use HTTP.

References: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/),
[websockets client API](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html).

Implementation checks passed: the combined focused suite has 10 passing tests,
and `check_client.mjs` passed all four live local client/network checks. The main
API's health behavior and rejection of `/ws/mock` were verified. This confirms
stream behavior without Docker; perform the browser exercise for visual review.
