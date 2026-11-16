import { useState } from "react";
import { displayValue, getContracts, getPrices, PRICE_UNIT } from "./api/market";
import type { ContractPoint, ContractResponse, TableNumber } from "./api/market";
import type { PriceRange } from "./mockMarket";
import { ContractsPanel, pointValue } from "./components/ContractsPanel";
import { PricePanel, selectedPrices } from "./components/PricePanel";
import { useResource } from "./components/useResource";

const loaders = {
  7: (signal: AbortSignal) => getContracts(7, signal), 8: (signal: AbortSignal) => getContracts(8, signal),
  9: (signal: AbortSignal) => getContracts(9, signal), 10: (signal: AbortSignal) => getContracts(10, signal),
};
function SnapshotCard({ title, value, detail, mock = false }: { title: string; value: string; detail: string; mock?: boolean }) {
  return <article className="card"><span className={`badge ${mock ? "" : "observed"}`}>{mock ? "Mock data" : "EIA · U.S."}</span>
    <h3>{title}</h3><p className="metric">{value}</p><p>{detail}</p>
    <small>{mock ? "Source: synthetic teaching fixture" : "Source: U.S. Energy Information Administration"}</small>
  </article>;
}
function latestCount(data: ContractResponse | null): ContractPoint | undefined {
  return data?.points.filter(point => point.series_id === "eia_t8_contract_count" && point.contract_type === "total").sort((a, b) => b.report_year - a.report_year)[0];
}
export function Dashboard() {
  const prices = useResource(getPrices);
  const resources = { 7: useResource(loaders[7]), 8: useResource(loaders[8]), 9: useResource(loaders[9]), 10: useResource(loaders[10]) };
  const [range, setRange] = useState<PriceRange>("all");
  const points = selectedPrices(prices.data, range);
  const latest = points[points.length - 1];
  const count = latestCount(resources[8].data);
  function priceDetail(key: "spot" | "longTerm") {
    if (!latest) return prices.loading ? "Loading mock prices from API." : "Mock prices unavailable; no local fallback.";
    const difference = latest[key] - points[0][key];
    return `Mock observation: ${latest.month}. ${difference >= 0 ? "+" : ""}${difference.toFixed(2)} ${PRICE_UNIT} since ${points[0].month}.`;
  }
  return <>
    <header><p className="eyebrow">Uranium market context</p><h1>Uranium Market Dashboard</h1><p>Price indicators, U.S. utility contracting, and the source context behind each view.</p></header>
    <aside className="notice" aria-label="Mock data notice"><strong>Prices are mock; contracting views use imported EIA data when available.</strong>
      <p>Cameco price import and display are pending reuse permission. All displayed price values are invented and are not expected to match Cameco’s published prices. EIA views identify their U.S.-only scope and report vintage.</p>
    </aside>
    <section aria-labelledby="snapshot-title"><h2 id="snapshot-title">Market snapshot</h2><div className="snapshots">
      <SnapshotCard mock title="Spot price indicator" value={latest ? `${latest.spot.toFixed(2)} ${PRICE_UNIT}` : "Unavailable"} detail={priceDetail("spot")} />
      <SnapshotCard mock title="Long-term price indicator" value={latest ? `${latest.longTerm.toFixed(2)} ${PRICE_UNIT}` : "Unavailable"} detail={priceDetail("longTerm")} />
      <SnapshotCard title="New contracts with same-year deliveries — U.S." value={count ? `${pointValue(count)}${count.value !== null ? " contracts" : ""}` : resources[8].loading ? "Loading…" : "Unavailable"} detail={count ? `Report year ${count.report_year}. Signed that year with deliveries received that year; not all new contracts. ${count.data_status}. Published/revised ${count.source_publication_date}.` : "EIA Table 8 data is unavailable. No mock count is substituted."} />
      <SnapshotCard title="Source freshness" value={count ? `EIA report ${count.report_year}` : "EIA unavailable"} detail={count ? `Annual source. Value-source retrieval: ${new Date(count.retrieved_at).toISOString()}. Mock prices have no publication or external retrieval date.` : "Mock prices have no external retrieval date. Each EIA view shows its own source dates when available."} />
    </div></section>
    <PricePanel resource={prices} range={range} setRange={setRange} />
    <ContractsPanel resources={resources as Record<TableNumber, typeof resources[7]>} />
    <section className="panel" aria-labelledby="reading-title"><h2 id="reading-title">How to read this dashboard</h2><dl>
      <dt>Signing year versus delivery year</dt><dd>Signing records when an agreement was made. Future delivery years describe what is contracted to arrive; actual deliveries describe material received. EIA’s minimum/maximum contract bounds are not probability scenarios.</dd>
      <dt>Price indicators versus transactions</dt><dd>Uranium contracts are privately negotiated. Published spot/long-term indicators are not prices for every sale. Our price chart remains synthetic; EIA delivery prices are different measures.</dd>
      <dt>Scope and aggregation</dt><dd>EIA covers U.S. civilian reactor owners/operators. No global Cameco/UxC contracting figures are merged here. Totals overlap their components. Different report vintages must stay separate.</dd>
      <dt>Suppression, dates, and uncertainty</dt><dd>Withheld values (W) and missing values remain unavailable. Source publication dates, observation/reporting periods, and value-source retrieval times have distinct meanings. Rows marked revised retain their source trail.</dd>
      <dt>Follow-on context</dt><dd>A scenario supply gap would not prove an observed shortage. Nuclear capacity is a demand driver, not a direct uranium-demand series. No unverified projection data is plotted.</dd>
    </dl>
    <details><summary>Worked example: trace a signing bar and compare an actual delivery</summary>
      <p>The Table 8 bar uses the total contract count for the reporting year. Its value has a unit of contracts, not uranium volume; open that row’s Source details for the workbook, publication date, vintage, checksum, and run.</p>
      <p>Switch to Table 7, All materials, Quantity to inspect actual deliveries with reported price. Its unit is thousand pounds U3O8 equivalent. It includes deliveries under existing contracts and cannot be interpreted as the Table 8 signing count.</p>
      {count && <p>Current Table 8 example: {displayValue(count.value)} contracts for report year {count.report_year}; source <a href={count.source_url}>{count.source_table} workbook</a>.</p>}
      <p>The table preserves API decimal values with display formatting; decimal strings become numbers only for chart coordinates. Source details retain the raw cell text.</p>
    </details>
    </section>
  </>;
}
