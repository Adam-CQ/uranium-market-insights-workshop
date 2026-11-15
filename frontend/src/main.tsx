import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { Dashboard } from "./Dashboard";

function App() {
  const [status, setStatus] = useState("Not checked");

  async function checkHealth() {
    setStatus("Checking…");
    try {
      const response = await fetch("/health");
      if (!response.ok) throw new Error("API unavailable");
      const data: unknown = await response.json();
      setStatus(
        typeof data === "object" && data !== null && "status" in data && data.status === "ok"
          ? "API is healthy"
          : "Unexpected API response",
      );
    } catch {
      setStatus("Cannot reach API. Check that the backend is running.");
    }
  }

  return (
    <main>
      <Dashboard />
      <section className="panel" aria-label="API connection">
      <h2>Local service connection</h2>
      <button onClick={checkHealth}>Check API connection</button>
      <p role="status">{status}</p>
      </section>
      <footer>Educational market information, not investment advice.</footer>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
