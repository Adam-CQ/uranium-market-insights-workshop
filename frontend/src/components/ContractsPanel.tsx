import { useMemo, useState } from "react";
import { MarketChart } from "../charts/MarketChart";
import { displayValue } from "../api/market";
import type { ContractPoint, ContractResponse, TableNumber } from "../api/market";
import { ResourceNotice } from "./useResource";
import type { Resource } from "./useResource";

export const TABLE_TITLES: Record<TableNumber, string> = {
  8: "New signings with same-year deliveries — EIA Table 8",
  9: "Future purchases from new signings — EIA Table 9",
  10: "Future purchases under existing contracts — EIA Table 10",
  7: "Actual deliveries with reported price — EIA Table 7",
};
const CONTRACT_LABELS = { spot: "Spot", long_term: "Long-term", total: "Total" };
const MEASURE_LABELS = { contract_count: "Contract count", quantity: "Quantity", price: "Weighted-average price" };
export interface Selection { year: string; measure: string; contract: string; material: string; supplier: string }
export function selectContractPoints(response: ContractResponse, table: TableNumber, selection: Selection): ContractPoint[] {
  return response.points.filter(point => {
    if (table === 8) return point.series_id === `eia_t8_${selection.measure}` && point.contract_type === selection.contract;
    if (point.report_year !== Number(selection.year)) return false;
    if (table === 7) return point.series_id === `eia_t7_${selection.material}_${selection.measure}`;
    return table === 9 || point.supplier_scope === selection.supplier;
  });
}
export function pointValue(point: ContractPoint) {
  return point.value_status === "available" ? displayValue(point.value) : point.value_status === "withheld" ? "Withheld (W)" : "Missing";
}
export function SourceDates({ points }: { points: ContractPoint[] }) {
  const publications = [...new Set(points.map(point => point.source_publication_date))].sort();
  const retrievals = [...new Set(points.map(point => point.retrieved_at))].sort();
  if (!points.length) return null;
  const oldPublication = Date.now() - Date.parse(publications[publications.length - 1]) > 400 * 86400000;
  return <div className="source-dates">
    <p>Report publication/revision: {publications.join(", ")}. Value-source retrieval (UTC): {retrievals.map(value => new Date(value).toISOString()).join(", ")}.</p>
    <p className="muted">Annual source snapshots; no real-time feed. Retrieval times refer to the artifacts that introduced these values.</p>
    {oldPublication && <p className="notice">Older annual publication: check EIA for a newer report. This reminder appears after 400 days; it does not establish that EIA has released a replacement.</p>}
  </div>;
}
function Provenance({ point }: { point: ContractPoint }) {
  return <details className="provenance"><summary>Source details</summary><dl>
    <dt>Source</dt><dd><a href={point.source_url}>{point.source_name} — {point.source_table} workbook</a></dd>
    <dt>Publication/revision date</dt><dd>{point.source_publication_date}</dd>
    <dt>Value-source retrieval (UTC)</dt><dd>{new Date(point.retrieved_at).toISOString()}</dd>
    <dt>Vintage</dt><dd>{point.source_vintage}</dd>
    <dt>Artifact SHA-256</dt><dd>{point.artifact_sha256}</dd>
    <dt>Ingestion run</dt><dd>{point.ingestion_run_id}</dd>
    <dt>Raw cell value</dt><dd>{point.raw_value || "Blank"}</dd>
    <dt>Quality/revision notes</dt><dd>{point.quality_notes}</dd>
  </dl></details>;
}
function ContractView({ response, table }: { response: ContractResponse; table: TableNumber }) {
  const years = [...new Set(response.points.map(point => point.report_year))].sort((a, b) => b - a);
  const [year, setYear] = useState(String(years[0] ?? ""));
  const [measure, setMeasure] = useState(table === 8 ? "contract_count" : "quantity");
  const [contract, setContract] = useState("total");
  const [material, setMaterial] = useState("total");
  const [supplier, setSupplier] = useState("all");
  const selected = useMemo(() => selectContractPoints(response, table, { year, measure, contract, material, supplier }), [response, table, year, measure, contract, material, supplier]);
  const plotted = selected.filter(point => table === 7 ? point.contract_type !== "total" : table === 8 || point.delivery_year !== null);
  const totals = selected.filter(point => table === 7 ? point.contract_type === "total" : table !== 8 && point.delivery_year === null);
  const unit = selected[0]?.unit ?? "";
  const categories = table === 8 ? plotted.map(point => String(point.report_year)).sort() : table === 7 ? ["spot", "long_term"] : [...new Set(plotted.map(point => String(point.delivery_year)))].sort();
  const key = (point: ContractPoint) => table === 8 ? String(point.report_year) : table === 7 ? point.contract_type! : String(point.delivery_year);
  const option = useMemo(() => ({
    animation: false, aria: { enabled: true, decal: { show: true } },
    color: ["#087e83", "#7746a4"],
    tooltip: { trigger: "axis", renderMode: "richText", confine: true, textStyle: { fontSize: 12 }, formatter: (params: unknown) => {
      const entries = Array.isArray(params) ? params : [params];
      const index = (entries[0] as { dataIndex?: number } | undefined)?.dataIndex ?? 0;
      const category = categories[index];
      return [table === 7 ? CONTRACT_LABELS[category as keyof typeof CONTRACT_LABELS] : category,
        ...plotted.filter(point => key(point) === category).map(point => `${point.quantity_bound ?? (table === 8 ? MEASURE_LABELS[measure as keyof typeof MEASURE_LABELS] : "Delivery")}: ${pointValue(point)}\n${point.unit}\nReport ${point.report_year} · delivery ${point.delivery_year ?? "horizon total"}\n${point.source_table} · ${point.data_status}\nPublished ${point.source_publication_date}`),
      ].join("\n");
    } },
    legend: { top: 0 },
    grid: { top: 65, right: 20, left: 32, bottom: 55, containLabel: true },
    xAxis: { type: "category", data: categories.map(category => table === 7 ? CONTRACT_LABELS[category as keyof typeof CONTRACT_LABELS] : category), axisLabel: { hideOverlap: true } },
    yAxis: { type: "value", min: 0, minInterval: unit === "contracts" ? 1 : undefined },
    series: (table === 9 || table === 10 ? ["minimum", "maximum"] : [null]).map(bound => ({
      name: bound ? `${bound === "minimum" ? "Minimum" : "Maximum"} contracted quantity` : table === 8 ? MEASURE_LABELS[measure as keyof typeof MEASURE_LABELS] : material === "total" ? "All materials" : material.replaceAll("_", " "),
      type: "bar", barMaxWidth: 64,
      data: categories.map(category => {
        const point = plotted.find(item => key(item) === category && (bound === null || item.quantity_bound === bound));
        return point?.value_status === "available" ? Number(point.value) : null;
      }),
    })),
  }), [selected, table, measure, material, unit]); // selected fixes the scope, units, and vintage for this chart.
  return <>
    <p><span className="badge observed">Published EIA data</span> <span className="scope-chip">U.S. civilian reactor owners/operators</span></p>
    <p>{response.covered_population}. No global Cameco/UxC contracting estimates are included.</p>
    <div className="controls">
      {table !== 8 && <label>Reporting year <select aria-label="Reporting year" value={year} onChange={event => setYear(event.target.value)}>{years.map(value => <option key={value}>{value}</option>)}</select></label>}
      {(table === 7 || table === 8) && <label>Measure <select aria-label="Measure" value={measure} onChange={event => setMeasure(event.target.value)}>
        {table === 8 && <option value="contract_count">Contract count</option>}<option value="quantity">Quantity</option><option value="price">Weighted-average price</option>
      </select></label>}
      {table === 8 && <label>Contract type <select aria-label="Contract type" value={contract} onChange={event => setContract(event.target.value)}><option value="total">Total contracts</option><option value="spot">Spot</option><option value="long_term">Long-term</option></select></label>}
      {table === 7 && <label>Material <select aria-label="Material" value={material} onChange={event => setMaterial(event.target.value)}><option value="total">All materials</option><option value="u3o8">U3O8</option><option value="natural_uf6">Natural UF6</option><option value="enriched_uranium">Enriched uranium</option></select></label>}
      {table === 10 && <label>Supplier scope <select aria-label="Supplier scope" value={supplier} onChange={event => setSupplier(event.target.value)}><option value="all">All suppliers</option><option value="us">U.S. suppliers</option><option value="foreign">Foreign suppliers</option></select></label>}
    </div>
    <p><strong>Unit: {unit || "unavailable"}.</strong> {table === 8 ? `Reporting years: ${years.join(", ")}. Annual observations only; missing years are not interpolated.` : `Reporting vintage: ${year}.`} {table === 8 && years.length === 1 && "Only one reporting year is imported; this is not a complete historical series."}</p>
    {table === 8 && <p>Counts cover contracts signed in the reporting year <strong>with deliveries received that year</strong>. Quantities are those same-year deliveries; prices are their weighted averages.</p>}
    {table === 7 && <p>Actual delivered quantities with reported price, by contract type and material. These are not new signings or future contracted purchases.</p>}
    {(table === 9 || table === 10) && <p>Minimum/maximum are contractual bounds, not probability scenarios or forecasts of actual deliveries. Each chart uses one reporting vintage.</p>}
    {!selected.length ? <p>No observations match these controls.</p> : <>
      <SourceDates points={selected} />
      <MarketChart option={option} label={`${TABLE_TITLES[table]} in ${unit}; exact values and status in the following table`} />
      {plotted.length > 0 && plotted.every(point => point.value === null) && <p role="status">All selected values are withheld or missing. No numeric bars are drawn.</p>}
      <p>Withheld/missing values have no bar and are not zero. The zero-based scale and single unit apply to this view only.</p>
      {totals.length > 0 && <p className="published-total">Published totals (not plotted with components): {totals.map(point => `${point.quantity_bound ?? "All contracts"}: ${pointValue(point)} ${point.unit}`).join("; ")}.</p>}
      <p className="muted">On narrow screens, scroll the data table horizontally to read every column and open source details.</p>
      <div className="table-scroll" tabIndex={0} aria-label="Scrollable EIA data table"><table className="contract-table">
        <caption>{TABLE_TITLES[table]} — selected values</caption>
        <thead><tr><th scope="col">Report year</th><th scope="col">Delivery period</th><th scope="col">Contract/bound</th><th scope="col">Value ({unit})</th><th scope="col">Data status</th><th scope="col">Provenance</th></tr></thead>
        <tbody>{selected.map(point => <tr key={`${point.series_id}-${point.report_year}-${point.delivery_year}-${point.contract_type}`}>
          <td>{point.report_year}</td><th scope="row">{point.period_label}</th><td>{point.quantity_bound ?? CONTRACT_LABELS[point.contract_type!] ?? "Not applicable"}</td><td>{pointValue(point)}</td><td>{point.data_status} · {point.value_status}</td><td><Provenance point={point} /></td>
        </tr>)}</tbody>
      </table></div>
      <details><summary>How to read this EIA chart</summary><ul>{response.caveats.map(caveat => <li key={caveat}>{caveat}</li>)}</ul></details>
    </>}
    <p>Source: <a href={response.source_page}>U.S. Energy Information Administration — Table {table}</a>. Original workbook links and dates appear in each row’s source details.</p>
  </>;
}
export function ContractsPanel({ resources }: { resources: Record<TableNumber, Resource<ContractResponse>> }) {
  const [table, setTable] = useState<TableNumber>(8);
  const resource = resources[table];
  return <section className="panel" aria-labelledby="contracts-title">
    <h2 id="contracts-title">U.S. utility contracting and deliveries — EIA</h2>
    <label htmlFor="contract-view">Contracting view </label><select id="contract-view" value={table} onChange={event => setTable(Number(event.target.value) as TableNumber)}>
      {([8, 9, 10, 7] as TableNumber[]).map(value => <option key={value} value={value}>{TABLE_TITLES[value]}</option>)}
    </select>
    <h3>{TABLE_TITLES[table]}</h3>
    <ResourceNotice resource={resource} />
    {resource.data && resource.data.points.length === 0 && <p>No EIA observations imported for this view. Import the workbook using the README instructions. No mock values are substituted.</p>}
    {resource.data && resource.data.points.length > 0 && <ContractView key={table} response={resource.data} table={table} />}
  </section>;
}
