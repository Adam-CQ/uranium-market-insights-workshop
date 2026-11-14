import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

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
      <h1>Uranium Market Dashboard</h1>
      <p>Understand uranium prices and U.S. utility contracting, with source dates and definitions.</p>
      <p>Project setup — market data will be added in later milestones.</p>
      <button onClick={checkHealth}>Check API connection</button>
      <p role="status">{status}</p>
      <footer>Educational market information, not investment advice.</footer>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
