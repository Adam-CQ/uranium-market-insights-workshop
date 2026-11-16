import { useMemo } from "react";
import { MarketChart } from "../charts/MarketChart";
import { displayValue, PRICE_UNIT } from "../api/market";
import type { PriceHistory } from "../api/market";
import type { PriceRange } from "../mockMarket";
import { CamecoGuide } from "./CamecoGuide";
import { ResourceNotice } from "./useResource";
import type { Resource } from "./useResource";

export function selectedPrices(data: PriceHistory | null, range: PriceRange) {
  const spot = data?.series.find(series => series.series_id === "uranium_spot")?.points ?? [];
  const term = data?.series.find(series => series.series_id === "uranium_long_term")?.points ?? [];
  const start = range === "3m" ? Math.max(0, spot.length - 3) : 0;
  return spot.slice(start).map((point, index) => ({ month: point.observation_month, spot: point.value, longTerm: term[start + index].value }));
}
export function PricePanel({ resource, range, setRange }: { resource: Resource<PriceHistory>; range: PriceRange; setRange: (range: PriceRange) => void }) {
  const points = useMemo(() => selectedPrices(resource.data, range), [resource.data, range]);
  const option = useMemo(() => ({
    animation: false, aria: { enabled: true },
    color: ["#087e83", "#7746a4"],
    tooltip: { trigger: "axis", renderMode: "richText", confine: true, valueFormatter: (value: unknown) => `${String(value)} ${PRICE_UNIT} · mock` },
    legend: { top: 0, data: ["Spot — mock", "Long-term — mock"] },
    grid: { top: 55, right: 22, left: 56, bottom: 55, containLabel: true },
    xAxis: { type: "category", data: points.map(p => p.month) },
    yAxis: { type: "value", min: 0, name: PRICE_UNIT, nameLocation: "end", nameTextStyle: { align: "left" } },
    series: [
      { name: "Spot — mock", type: "line", data: points.map(p => p.spot), symbol: "circle", connectNulls: false },
      { name: "Long-term — mock", type: "line", data: points.map(p => p.longTerm), symbol: "diamond", lineStyle: { type: "dashed" }, connectNulls: false },
    ],
  }), [points]);
  return <section className="panel" aria-labelledby="prices-title">
    <h2 id="prices-title">Uranium price history — mock data</h2>
    <p><span className="badge">Mock prices</span> {PRICE_UNIT} · monthly synthetic indicators</p>
    <p>Cameco import and display are pending reuse permission. Source: synthetic teaching fixture served by our API. No Cameco price observations are displayed.</p>
    <ResourceNotice resource={resource} />
    {resource.data && points.length > 0 && <>
      <label htmlFor="price-range">Time range </label>
      <select id="price-range" value={range} onChange={event => setRange(event.target.value as PriceRange)}>
        <option value="all">All mock months</option><option value="3m">Last 3 mock months</option>
      </select>
      <p aria-live="polite">Showing {points[0].month} through {points[points.length - 1].month}. Snapshot changes use this range.</p>
      <p>Last mock observation: {points[points.length - 1].month}. Publication date and external retrieval time: unavailable.</p>
      <MarketChart option={option} label="Mock uranium price history; exact values in the following table" />
      <div className="table-scroll"><table>
        <caption>Mock price values — USD per pound U3O8</caption>
        <thead><tr><th scope="col">Observation month</th><th scope="col">Spot indicator</th><th scope="col">Long-term indicator</th></tr></thead>
        <tbody>{points.map(point => <tr key={point.month}><th scope="row">{point.month}</th><td>{displayValue(point.spot)}</td><td>{displayValue(point.longTerm)}</td></tr>)}</tbody>
      </table></div>
      <details><summary>Price methodology and source status</summary>
        <p>{resource.data.disclaimer}</p>
        <p>Straight lines connect monthly synthetic samples; no provider methodology or transaction feed is implemented.</p>
        {resource.data.series.map(series => <p key={series.series_id}>{series.provenance.source_name}: {series.provenance.methodology_notes}</p>)}
      </details>
    </>}
    {resource.data && points.length === 0 && <p>No mock price observations are available.</p>}
    <CamecoGuide />
  </section>;
}
