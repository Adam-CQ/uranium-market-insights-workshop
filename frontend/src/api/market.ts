// Validate server JSON before charting; TypeScript alone cannot validate HTTP data.
export const EIA_POPULATION = "Owners and operators of U.S. civilian nuclear power reactors";
export const PRICE_UNIT = "USD/lb U3O8";
export const QUANTITY_UNIT = "thousand lb U3O8 equivalent";
export type TableNumber = 7 | 8 | 9 | 10;
export interface PriceSeries {
  series_id: "uranium_spot" | "uranium_long_term";
  unit: string;
  currency: string;
  provenance: { source_name: string; data_status: "mock"; methodology_notes: string };
  points: { observation_month: string; value: number }[];
}
export interface PriceHistory { series: PriceSeries[]; disclaimer: string }
export interface ContractPoint {
  series_id: string; label: string; measure_type: string;
  value: string | null; raw_value: string;
  value_status: "available" | "withheld" | "missing";
  data_status: "observed" | "revised";
  unit: string; currency: string | null;
  report_year: number; delivery_year: number | null; period_label: string;
  contract_type: "spot" | "long_term" | "total" | null;
  material_type: string | null; supplier_scope: string | null;
  quantity_bound: "minimum" | "maximum" | null;
  source_name: string; source_url: string; source_table: string;
  source_publication_date: string; source_vintage: string; retrieved_at: string;
  artifact_sha256: string; ingestion_run_id: number; quality_notes: string;
}
export interface ContractResponse {
  scope: "us"; geography: "United States"; covered_population: string;
  table: TableNumber; source_page: string; data_status: "available" | "unavailable";
  points: ContractPoint[]; caveats: string[];
}
function assert(condition: unknown): asserts condition {
  if (!condition) throw new Error("Unexpected API data format. Check the API contract before displaying values.");
}
function record(value: unknown): asserts value is Record<string, unknown> {
  assert(typeof value === "object" && value !== null && !Array.isArray(value));
}
function string(value: unknown): asserts value is string { assert(typeof value === "string"); }
function nullableString(value: unknown) { assert(value === null || typeof value === "string"); }
function safeEiaLink(value: unknown) {
  string(value);
  const url = new URL(value);
  assert(url.protocol === "https:" && url.hostname === "www.eia.gov" && url.pathname.startsWith("/uranium/marketing/"));
}
function validMonth(value: unknown): value is string {
  return typeof value === "string" && /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value) && !value.startsWith("0000");
}
export function parsePrices(value: unknown): PriceHistory {
  record(value); string(value.disclaimer);
  assert(Array.isArray(value.series) && value.series.length === 2);
  const ids = new Set<string>();
  for (const series of value.series) {
    record(series);
    assert(series.series_id === "uranium_spot" || series.series_id === "uranium_long_term");
    assert(!ids.has(series.series_id)); ids.add(series.series_id);
    assert(series.unit === PRICE_UNIT && series.currency === "USD");
    record(series.provenance);
    assert(series.provenance.data_status === "mock");
    string(series.provenance.source_name); string(series.provenance.methodology_notes);
    assert(Array.isArray(series.points));
    let previous = "";
    for (const point of series.points) {
      record(point); assert(validMonth(point.observation_month));
      assert(point.observation_month > previous); previous = point.observation_month;
      assert(typeof point.value === "number" && Number.isFinite(point.value) && point.value >= 0);
    }
  }
  const result = value as unknown as PriceHistory;
  assert(JSON.stringify(result.series[0].points.map(p => p.observation_month)) === JSON.stringify(result.series[1].points.map(p => p.observation_month)));
  return result;
}
export function parseContracts(value: unknown, table: TableNumber): ContractResponse {
  record(value);
  assert(value.scope === "us" && value.geography === "United States" && value.covered_population === EIA_POPULATION && value.table === table);
  safeEiaLink(value.source_page);
  assert(value.data_status === "available" || value.data_status === "unavailable");
  assert(Array.isArray(value.caveats) && value.caveats.every(c => typeof c === "string"));
  assert(Array.isArray(value.points));
  assert((value.points.length > 0) === (value.data_status === "available"));
  const identities = new Set<string>();
  for (const point of value.points) {
    record(point);
    for (const field of ["series_id", "label", "measure_type", "raw_value", "period_label", "source_name", "source_table", "source_publication_date", "source_vintage", "retrieved_at", "artifact_sha256", "quality_notes"]) string(point[field]);
    assert((point.series_id as string).startsWith(`eia_t${table}_`));
    assert(point.source_table === `EIA Table ${table}`);
    const suffix = (point.series_id as string).replace(`eia_t${table}_`, "");
    assert(table === 7 ? /^(u3o8|natural_uf6|enriched_uranium|total)_(quantity|price)$/.test(suffix) : table === 8 ? ["quantity", "price", "contract_count"].includes(suffix) : table === 9 ? ["minimum", "maximum"].includes(suffix) : /^(us|foreign|all)_(minimum|maximum)$/.test(suffix));
    const expectedUnit = suffix.endsWith("price") ? "USD/lb U3O8 equivalent" : suffix === "contract_count" ? "contracts" : QUANTITY_UNIT;
    assert(point.unit === expectedUnit);
    if (table === 7) assert(point.material_type === suffix.replace(/_(quantity|price)$/, ""));
    if (table === 10) assert(point.supplier_scope === suffix.replace(/_(minimum|maximum)$/, ""));
    if (table === 9 || table === 10) assert(point.quantity_bound === (suffix.endsWith("minimum") ? "minimum" : "maximum"));

    assert(point.unit === QUANTITY_UNIT || point.unit === "USD/lb U3O8 equivalent" || point.unit === "contracts");
    assert(point.currency === (point.unit === "USD/lb U3O8 equivalent" ? "USD" : null));
    assert(Number.isInteger(point.report_year) && Number(point.report_year) >= 1900 && Number(point.report_year) <= 9998);
    assert(point.delivery_year === null || Number.isInteger(point.delivery_year));
    if (table === 7 || table === 8) assert(point.delivery_year === point.report_year);
    else assert(point.delivery_year === null || Number(point.delivery_year) > Number(point.report_year));
    assert(["spot", "long_term", "total", null].includes(point.contract_type as string | null));
    nullableString(point.material_type); nullableString(point.supplier_scope);
    assert(["minimum", "maximum", null].includes(point.quantity_bound as string | null));
    assert(point.data_status === "observed" || point.data_status === "revised");
    assert(["available", "withheld", "missing"].includes(point.value_status as string));
    if (point.value_status === "available") {
      string(point.value); assert(/^[0-9]+(\.[0-9]+)?$/.test(point.value));
      assert(Number.isFinite(Number(point.value)) && Number(point.value) <= Number.MAX_SAFE_INTEGER);
    } else assert(point.value === null);
    safeEiaLink(point.source_url);
    assert(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(point.source_publication_date as string));
    assert(Number.isFinite(Date.parse(point.source_publication_date as string)) && Number.isFinite(Date.parse(point.retrieved_at as string)));
    assert(/^[a-f0-9]{64}$/.test(point.artifact_sha256 as string) && Number.isInteger(point.ingestion_run_id));
    const id = JSON.stringify([point.series_id, point.report_year, point.delivery_year, point.contract_type]);
    assert(!identities.has(id)); identities.add(id);
  }
  return value as unknown as ContractResponse;
}
async function request(path: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(`API request failed (HTTP ${response.status}). Check the API, database, and imports.`);
  return response.json();
}
export function getPrices(signal: AbortSignal) {
  return request("/api/v1/prices/uranium", signal).then(parsePrices);
}
export function contractPath(table: TableNumber) {
  return table === 7 ? "/api/v1/contracts/deliveries?scope=us" : table === 8 ? "/api/v1/contracts/signings?scope=us" : `/api/v1/contracts/future-deliveries?scope=us&table=${table}`;
}
export function getContracts(table: TableNumber, signal: AbortSignal) {
  return request(contractPath(table), signal).then(value => parseContracts(value, table));
}
export function displayValue(value: string | number | null): string {
  if (value === null) return "Unavailable";
  const [integer, fraction] = String(value).split(".");
  const digits = fraction?.replace(/0+$/, "");
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (digits ? `.${digits}` : "");
}
