// Exercise the actual browser script in jsdom using real local WebSocket frames.
// Uses the frontend's already-approved dev dependencies; no Docker is required.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import net from "node:net";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
import { JSDOM, VirtualConsole } from "../../frontend/node_modules/jsdom/lib/api.js";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = fileURLToPath(new URL("../../backend/.venv/bin/python", import.meta.url));
const listener = net.createServer();
listener.listen(0, "127.0.0.1");
await once(listener, "listening");
const port = listener.address().port;
await new Promise(resolve => listener.close(resolve));
const url = `http://127.0.0.1:${port}`;
let server = null;
let window = null;
let serverLog = "";

async function waitUntil(check, message, timeout = 10000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await check()) return;
    await delay(25);
  }
  throw new Error(`${message}\n${serverLog}`);
}
async function startServer() {
  serverLog = "";
  server = spawn(python, ["-m", "uvicorn", "examples.websocket_demo.server:app", "--host", "127.0.0.1", "--port", String(port)], { cwd: root, stdio: ["ignore", "ignore", "pipe"] });
  let launchError = null;
  server.on("error", error => { launchError = error; });
  server.stderr.on("data", data => { serverLog = (serverLog + data).slice(-4000); });
  await waitUntil(async () => {
    if (launchError) throw launchError;
    if (server.exitCode !== null) throw new Error(`Example server exited: ${serverLog}`);
    try { return (await fetch(url)).ok; } catch { return false; }
  }, "Example HTTP server did not start");
}
async function stopServer() {
  if (!server || server.exitCode !== null) { server = null; return; }
  const current = server;
  const closed = once(current, "close");
  current.kill("SIGTERM");
  const guard = setTimeout(() => current.kill("SIGKILL"), 5000);
  try { await closed; } finally { clearTimeout(guard); server = null; }
}
try {
  await startServer();
  const virtualConsole = new VirtualConsole();
  const jsErrors = [];
  virtualConsole.on("jsdomError", error => {
    // Network failure while the server is deliberately stopped is expected.
    if (error.message.includes("Uncaught")) jsErrors.push(error.message);
  });
  const dom = await JSDOM.fromURL(url, { runScripts: "dangerously", resources: "usable", virtualConsole });
  window = dom.window;
  await new Promise(resolve => window.addEventListener("load", resolve));
  const document = window.document;
  const status = () => document.getElementById("status").textContent;
  const connection = () => document.getElementById("connection-id").textContent;
  const messages = () => document.getElementById("messages").textContent;
  document.getElementById("connect").click();
  await waitUntil(() => Number(document.getElementById("sequence").textContent) >= 2, "Client did not receive two pushed messages");
  const payloads = messages().split("\n").map(line => JSON.parse(line));
  assert.equal(payloads[0].sequence, 1);
  assert.equal(payloads[0].value, 100);
  assert.equal(payloads[1].sequence, 2);
  assert.equal(payloads[0].data_status, "mock");
  const firstConnection = connection();
  process.stdout.write("PASS actual client receives validated mock messages without per-message requests\n");

  document.getElementById("disconnect").click();
  await waitUntil(() => status() === "Disconnected by user", "Manual disconnect state missing");
  const stoppedMessages = messages();
  await delay(1200);
  assert.equal(messages(), stoppedMessages);
  assert.equal(status(), "Disconnected by user");
  process.stdout.write("PASS manual disconnect cancels streaming and retries\n");

  document.getElementById("connect").click();
  await waitUntil(() => connection() !== firstConnection, "Manual reconnect did not establish a new connection");
  const beforeRestart = connection();
  await stopServer();
  await waitUntil(() => status().includes("Reconnecting"), "Server stop was not reflected in retry status");
  process.stdout.write("PASS server stop reaches disconnected/retrying state\n");
  await startServer();
  await waitUntil(() => status().startsWith("Connected") && connection() !== beforeRestart, "Client did not reconnect after server restart");
  const resumed = messages().split("\n").map(line => JSON.parse(line)).filter(message => message.connection_id === connection());
  assert.equal(resumed[0].sequence, 1);
  assert.equal(resumed[0].value, 100);
  assert.deepEqual(jsErrors, []);
  process.stdout.write("PASS automatic reconnect receives a new stream starting at sequence 1\n");
  document.getElementById("disconnect").click();
} finally {
  window?.close();
  await stopServer();
}
