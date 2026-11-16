// Standalone browser client. Reconnect behavior is intentionally explicit.
const connectButton = document.getElementById("connect");
const disconnectButton = document.getElementById("disconnect");
const reconnect = document.getElementById("reconnect");
const status = document.getElementById("status");
const messages = document.getElementById("messages");
const connectionId = document.getElementById("connection-id");
const sequence = document.getElementById("sequence");
let socket = null;
let timer = null;
let retries = 0;
let wanted = false;
const received = [];

function cancelRetry() {
  clearTimeout(timer);
  timer = null;
}
function openConnection() {
  cancelRetry();
  if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) return;
  wanted = true;
  connectButton.disabled = true;
  disconnectButton.disabled = false;
  status.textContent = "Connecting…";
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const current = new WebSocket(`${protocol}//${location.host}/ws/mock`);
  socket = current;
  current.onopen = () => {
    if (socket !== current) return;
    retries = 0;
    status.textContent = "Connected — mock stream";
  };
  current.onmessage = event => {
    if (socket !== current) return;
    try {
      const message = JSON.parse(event.data);
      if (message.data_status !== "mock" || !Number.isInteger(message.sequence) || message.sequence < 1 ||
          typeof message.value !== "number" || !Number.isFinite(message.value) || message.value < 0 ||
          typeof message.connection_id !== "string" || !/^[0-9a-f-]{36}$/.test(message.connection_id)) {
        throw new Error("Invalid mock message shape");
      }
      connectionId.textContent = message.connection_id;
      sequence.textContent = String(message.sequence);
      received.push(JSON.stringify(message));
      if (received.length > 50) received.shift();
      messages.textContent = received.join("\n");
    } catch {
      status.textContent = "Rejected an invalid message; expected labelled synthetic data.";
    }
  };
  current.onerror = () => {
    if (socket === current) status.textContent = "Connection error — waiting for disconnect/retry";
  };
  current.onclose = event => {
    if (socket !== current) return;
    socket = null;
    connectButton.disabled = false;
    disconnectButton.disabled = true;
    if (wanted && reconnect.checked) {
      const delay = Math.min(1000 * 2 ** retries, 8000);
      retries = Math.min(retries + 1, 3);
      status.textContent = `Disconnected (code ${event.code}). Reconnecting in ${delay / 1000}s…`;
      disconnectButton.disabled = false; // Lets the user cancel a queued retry.
      timer = setTimeout(openConnection, delay);
    } else {
      status.textContent = wanted ? "Disconnected — automatic reconnect is off" : "Disconnected by user";
    }
  };
}
connectButton.addEventListener("click", openConnection);
disconnectButton.addEventListener("click", () => {
  wanted = false;
  cancelRetry();
  status.textContent = "Disconnected by user";
  connectButton.disabled = false;
  disconnectButton.disabled = true;
  socket?.close(1000, "User disconnected");
});
reconnect.addEventListener("change", () => {
  if (!reconnect.checked) {
    cancelRetry();
    if (!socket) {
      status.textContent = "Disconnected — automatic reconnect is off";
      disconnectButton.disabled = true;
    }
  } else if (wanted && !socket) {
    openConnection();
  }
});
