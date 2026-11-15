import { useState } from "react";
import { mockContracting, mockPrices, selectPrices } from "./mockMarket";
import type { PriceRange, UraniumPricePoint } from "./mockMarket";

function SnapshotCard({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <article className="card">
      <span className="badge">Mock data</span>
      <h3>{title}</h3>
      <p className="metric">{value}</p>
      <p>{detail}</p>
      <small>Source: synthetic teaching fixture</small>
    </article>
  );
}

function PriceChart({ points }: { points: UraniumPricePoint[] }) {
  // A fixed zero-based scale makes range comparisons honest in this placeholder.
  const x = (index: number) => 60 + index * (600 / Math.max(points.length - 1, 1));
  const y = (value: number) => 230 - value * 2;
  const line = (key: "spot" | "longTerm") => points.map((point, index) => `${x(index)},${y(point[key])}`).join(" ");

  return (
    <>
      <div className="legend"><span>Solid teal: spot indicator</span><span>Dashed purple: long-term indicator</span></div>
      <svg className="price-chart" viewBox="0 0 720 280" role="img" aria-labelledby="chart-title" aria-describedby="chart-description">
        <title id="chart-title">Mock uranium price history</title>
        <desc id="chart-description">Synthetic spot and long-term indicators in USD per pound U3O8. Exact values appear in the following table.</desc>
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line x1="60" x2="660" y1={y(value)} y2={y(value)} stroke="#d9e2e8" />
            <text x="48" y={y(value) + 4} textAnchor="end">{value}</text>
          </g>
        ))}
        <polyline points={line("spot")} fill="none" stroke="#087e83" strokeWidth="3" />
        <polyline points={line("longTerm")} fill="none" stroke="#7746a4" strokeWidth="3" strokeDasharray="8 5" />
        {points.map((point, index) => <text key={point.month} x={x(index)} y="257" textAnchor="middle">{point.month}</text>)}
      </svg>
      <div className="table-scroll">
        <table>
          <caption>Mock price values — USD per pound U3O8</caption>
          <thead><tr><th scope="col">Observation month</th><th scope="col">Spot indicator</th><th scope="col">Long-term indicator</th></tr></thead>
          <tbody>{points.map((point) => <tr key={point.month}><th scope="row">{point.month}</th><td>{point.spot.toFixed(2)}</td><td>{point.longTerm.toFixed(2)}</td></tr>)}</tbody>
        </table>
      </div>
    </>
  );
}

export function Dashboard() {
  const [range, setRange] = useState<PriceRange>("all");
  const points = selectPrices(mockPrices, range);
  const latest = mockPrices[mockPrices.length - 1];
  const first = points[0];
  const change = (key: "spot" | "longTerm") => {
    const difference = latest[key] - first[key];
    return `${difference >= 0 ? "+" : ""}${difference.toFixed(2)} USD/lb U3O8 since ${first.month}`;
  };

  return (
    <>
      <header>
        <p className="eyebrow">Market context · workshop preview</p>
        <h1>Uranium Market Dashboard</h1>
        <p>Explore price indicators and U.S. utility contracting with clear definitions and dates.</p>
      </header>
      <aside className="notice" aria-label="Mock data notice">
        <strong>Mock data — all market values are invented.</strong> This preview contains no Cameco or EIA observations. Dates and units demonstrate the future interface.
        <p>Cameco price import and display are pending reuse permission. We will continue showing synthetic prices; these values are not expected to match Cameco’s published prices.</p>
      </aside>
      <section aria-labelledby="snapshot-title">
        <h2 id="snapshot-title">Market snapshot</h2>
        <div className="snapshots">
          <SnapshotCard title="Spot price indicator" value={`${latest.spot.toFixed(2)} USD/lb U3O8`} detail={`Mock observation: ${latest.month}. ${change("spot")}.`} />
          <SnapshotCard title="Long-term price indicator" value={`${latest.longTerm.toFixed(2)} USD/lb U3O8`} detail={`Mock observation: ${latest.month}. ${change("longTerm")}.`} />
          <SnapshotCard title="Newly signed contracts — U.S." value={`${mockContracting.contractCount} contracts`} detail={`Mock reporting year: ${mockContracting.reportingYear}. ${mockContracting.scope}. Annual signings, not deliveries.`} />
          <SnapshotCard title="Data freshness" value="No source retrieved" detail="Local mock fixture only. Publication and retrieval dates are unavailable. Price and contracting sources will update on different schedules." />
        </div>
      </section>
      <section className="panel" aria-labelledby="prices-title">
        <h2 id="prices-title">Uranium price history — mock data</h2>
        <p>USD per pound U3O8 · last mock observation: {latest.month} · monthly sample</p>
        <label htmlFor="price-range">Time range </label>
        <select id="price-range" value={range} onChange={(event) => setRange(event.target.value as PriceRange)}>
          <option value="all">All 6 mock months</option>
          <option value="3m">Last 3 mock months</option>
        </select>
        <p className="range-description" aria-live="polite">Showing {points[0].month} through {latest.month}. Snapshot changes use this range.</p>
        <PriceChart points={points} />
        <p className="muted">Source: synthetic teaching fixture. The placeholder connects monthly sample values with straight lines; it does not implement provider methodology.</p>
      </section>
      <section className="panel" aria-labelledby="reading-title">
        <h2 id="reading-title">How to read this dashboard</h2>
        <dl>
          <dt>Price indicators</dt><dd>Spot and long-term indicators describe different market conditions. Uranium contracts are privately negotiated; an indicator is not the price of every sale.</dd>
          <dt>Signings and deliveries</dt><dd>A contract signing year records when an agreement was made. Delivery years record when uranium is due or was delivered. The mock signing count is not a delivery quantity.</dd>
          <dt>Scope and freshness</dt><dd>The planned EIA view covers U.S. civilian reactor owners/operators, not the global market. Observation periods, source publication dates, and retrieval times will be shown separately when real data is connected.</dd>
        </dl>
      </section>
    </>
  );
}
