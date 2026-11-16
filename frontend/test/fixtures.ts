// Compact offline API test doubles. Never imported into the application bundle.
import type { ContractPoint, ContractResponse, PriceHistory, TableNumber } from "../src/api/market";
import { EIA_POPULATION, PRICE_UNIT, QUANTITY_UNIT } from "../src/api/market";
import { mockPrices } from "../src/mockMarket";

export const prices: PriceHistory = {
  disclaimer: "Synthetic teaching data only; not Cameco observations.",
  series: (["uranium_spot", "uranium_long_term"] as const).map((id, index) => ({
    series_id: id, unit: PRICE_UNIT, currency: "USD",
    provenance: { source_name: "Synthetic teaching fixture", data_status: "mock", methodology_notes: "Invented monthly indicators, not transaction prices." },
    points: mockPrices.map(point => ({ observation_month: point.month, value: index === 0 ? point.spot : point.longTerm })),
  })),
};
function point(table: TableNumber, suffix: string, value: string | null, changes: Partial<ContractPoint> = {}): ContractPoint {
  const unit = suffix.endsWith("price") ? "USD/lb U3O8 equivalent" : suffix === "contract_count" ? "contracts" : QUANTITY_UNIT;
  return {
    series_id: `eia_t${table}_${suffix}`, label: suffix === "contract_count" ? "Contracts signed in reporting year with deliveries received that year" : suffix.replaceAll("_", " "),
    measure_type: suffix === "contract_count" ? "signed_contracts_with_same_year_deliveries" : "test_measure",
    value, raw_value: value ?? "W", value_status: value === null ? "withheld" : "available", data_status: "observed",
    unit, currency: unit.startsWith("USD") ? "USD" : null,
    report_year: 2025, delivery_year: table === 7 || table === 8 ? 2025 : 2026, period_label: table === 7 || table === 8 ? "2025" : "2026",
    contract_type: null, material_type: table === 7 ? suffix.replace(/_(quantity|price)$/, "") : null,
    supplier_scope: table === 10 ? suffix.replace(/_(minimum|maximum)$/, "") : null,
    quantity_bound: table === 9 || table === 10 ? (suffix.endsWith("minimum") ? "minimum" : "maximum") : null,
    source_name: "U.S. Energy Information Administration", source_url: `https://www.eia.gov/uranium/marketing/xls/test-table${table}.xlsx`,
    source_table: `EIA Table ${table}`, source_publication_date: "2026-08-13", source_vintage: "offline-test-vintage-2025",
    retrieved_at: "2026-11-15T12:00:00Z", artifact_sha256: "a".repeat(64), ingestion_run_id: table,
    quality_notes: "Offline API test double; values and withheld cases are representative, not a full workbook.", ...changes,
  };
}
export function contracts(table: TableNumber): ContractResponse {
  const points: ContractPoint[] = [];
  if (table === 8) {
    const kinds = ["spot", "long_term", "total"] as const;
    const values = { contract_count: ["17", "5", "22"], quantity: ["2901", "1420", "4321"], price: ["70.01", "71.37", "70.46"] };
    for (const [measure, numbers] of Object.entries(values)) kinds.forEach((contract_type, index) => points.push(point(table, measure, numbers[index], { contract_type })));
  } else if (table === 7) {
    for (const material of ["total", "u3o8", "natural_uf6", "enriched_uranium"]) {
      const quantities = material === "total" ? ["5997.5", "40854", "46851.5"] : material === "u3o8" ? ["5679.5", "29939.2", "35618.7"] : [null, null, null];
      (["spot", "long_term", "total"] as const).forEach((contract_type, index) => {
        points.push(point(table, `${material}_quantity`, quantities[index], { contract_type }));
        points.push(point(table, `${material}_price`, quantities[index] === null ? null : "58.46", { contract_type }));
      });
    }
  } else {
    for (const supplier of (table === 9 ? [""] : ["all_", "us_", "foreign_"])) {
      for (const bound of ["minimum", "maximum"]) {
        const withheldSupplier = supplier === "us_" || supplier === "foreign_";
        points.push(point(table, supplier + bound, withheldSupplier ? null : table === 9 ? "1511" : bound === "minimum" ? "36650" : "42016"));
        points.push(point(table, supplier + bound, null, { delivery_year: 2033, period_label: "2033" }));
        const horizon = table === 9 ? (bound === "minimum" ? "8865" : "12938")
          : supplier === "us_" ? (bound === "minimum" ? "1317" : "1548")
          : supplier === "foreign_" ? (bound === "minimum" ? "131191" : "172548")
          : (bound === "minimum" ? "132508" : "174095");
        points.push(point(table, supplier + bound, horizon, { delivery_year: null, period_label: "2026–2035 total" }));
      }
    }
  }
  return { scope: "us", geography: "United States", covered_population: EIA_POPULATION, table,
    source_page: `https://www.eia.gov/uranium/marketing/table${table}.php`, data_status: "available", points,
    caveats: ["U.S. civilian reactor owners/operators only; not global utility contracting.", "W is withheld, not zero. Totals overlap components."] };
}
export function fixtureForUrl(url: string) {
  if (url.includes("/prices/uranium")) return prices;
  if (url.includes("/signings")) return contracts(8);
  if (url.includes("/deliveries?")) return contracts(7);
  return contracts(url.includes("table=10") ? 10 : 9);
}
