// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Dashboard } from "./Dashboard";
import { contracts, fixtureForUrl, prices } from "../test/fixtures";
import { parseContracts, parsePrices, QUANTITY_UNIT } from "./api/market";
import { selectContractPoints } from "./components/ContractsPanel";

// DOM tests check controls/data tables; Playwright exercises the actual ECharts renderer.
vi.mock("./charts/MarketChart", () => ({ MarketChart: ({ label }: { label: string }) => <div role="img" aria-label={label} /> }));
const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockImplementation(async (url: string) => ({ ok: true, json: async () => structuredClone(fixtureForUrl(url)) }));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe("dashboard API integration", () => {
  it("separates mock prices and published U.S. EIA snapshot with dates and source", async () => {
    render(<Dashboard />);
    const snapshot = screen.getByRole("region", { name: "Market snapshot" });
    await within(snapshot).findByText("22 contracts");
    expect(within(snapshot).getByText("76.00 USD/lb U3O8")).toBeTruthy();
    expect(within(snapshot).getAllByText("Mock data")).toHaveLength(2);
    expect(screen.getByRole("complementary", { name: "Mock data notice" }).textContent).toContain("Prices are mock");
    const panel = screen.getByRole("region", { name: "U.S. utility contracting and deliveries — EIA" });
    expect(within(panel).getByText(/Reporting years: 2025/)).toBeTruthy();
    expect(within(panel).getByText(/Report publication\/revision: 2026-08-13/)).toBeTruthy();
    expect(within(panel).getByRole("link", { name: /U.S. Energy Information Administration — Table 8/ }).getAttribute("href")).toContain("table8.php");
    expect(panel.textContent).toContain("U.S. civilian reactor owners/operators");
    expect(panel.textContent).toContain("with deliveries received that year");
  });
  it("updates both mock chart selection and accessible table from API values", async () => {
    render(<Dashboard />);
    const table = await screen.findByRole("table", { name: "Mock price values — USD per pound U3O8" });
    expect(within(table).getAllByRole("row")).toHaveLength(7);
    fireEvent.change(screen.getByRole("combobox", { name: "Time range" }), { target: { value: "3m" } });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).queryByText("2025-01")).toBeNull();
    expect(screen.getAllByText(/\+2.00 USD\/lb U3O8 since 2025-04/)).toHaveLength(2);
  });
  it("keeps future vintages, units, withheld values and horizon totals explicit", async () => {
    render(<Dashboard />);
    await screen.findByText("22 contracts");
    fireEvent.change(screen.getByRole("combobox", { name: "Contracting view" }), { target: { value: "9" } });
    const table = screen.getByRole("table", { name: /Future purchases from new signings/ });
    expect(table.textContent).toContain("2026–2035 total");
    expect(table.textContent).toContain("Withheld (W)");
    expect(table.textContent).toContain(QUANTITY_UNIT);
    expect((screen.getByRole("combobox", { name: "Reporting year" }) as HTMLSelectElement).value).toBe("2025");
    fireEvent.change(screen.getByRole("combobox", { name: "Contracting view" }), { target: { value: "10" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Supplier scope" }), { target: { value: "us" } });
    expect(screen.getByText(/All plotted component values are withheld/)).toBeTruthy();
    expect(screen.getByText(/Published totals \(not plotted with components\)/).textContent).toContain("1,317");
    fireEvent.change(screen.getByRole("combobox", { name: "Contracting view" }), { target: { value: "7" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Material" }), { target: { value: "natural_uf6" } });
    expect(screen.getByText(/All plotted component values are withheld/)).toBeTruthy();
  });
  it("shows explicit failure and retries without replacing missing EIA data with a mock count", async () => {
    fetchMock.mockImplementation(async (url: string) => url.includes("/signings") ? ({ ok: false, status: 503 }) : ({ ok: true, json: async () => fixtureForUrl(url) }));
    render(<Dashboard />);
    await screen.findByRole("alert");
    expect(screen.queryByText("22 contracts")).toBeNull();
    expect(screen.getByText(/EIA Table 8 data is unavailable/)).toBeTruthy();
    fetchMock.mockImplementation(async (url: string) => ({ ok: true, json: async () => fixtureForUrl(url) }));
    fireEvent.click(screen.getByRole("button", { name: "Retry data request" }));
    await screen.findByText("22 contracts");
  });
  it("shows empty imports as unavailable and keeps mock prices visible", async () => {
    fetchMock.mockImplementation(async (url: string) => ({ ok: true, json: async () => url.includes("/signings") ? { ...contracts(8), data_status: "unavailable", points: [] } : fixtureForUrl(url) }));
    render(<Dashboard />);
    await screen.findByText(/No EIA observations imported/);
    expect(screen.queryByText("22 contracts")).toBeNull();
    await screen.findByText("76.00 USD/lb U3O8");
  });
  it("flags older annual publications for freshness review", async () => {
    const older = contracts(8);
    older.points.forEach(point => { point.source_publication_date = "2024-01-01"; });
    fetchMock.mockImplementation(async (url: string) => ({ ok: true, json: async () => url.includes("/signings") ? older : fixtureForUrl(url) }));
    render(<Dashboard />);
    await screen.findByText(/Older annual publication: check EIA/);
    expect(screen.getByText(/This reminder appears after 400 days/)).toBeTruthy();
  });
  it("provides the manual guide with official links and the mock verification boundary", async () => {
    render(<Dashboard />);
    fireEvent.click(screen.getByText("Check Cameco prices manually"));
    const guide = screen.getByText("Check Cameco prices manually").closest("details")!;
    expect(guide.open).toBe(true);
    expect(within(guide).getByRole("link", { name: "Cameco — Uranium Price" }).getAttribute("href")).toBe("https://www.cameco.com/invest/markets/uranium-price");
    expect(within(guide).getByRole("link", { name: "Terms of Use" })).toBeTruthy();
    expect(guide.textContent).toContain("does not import, refresh, or validate our mock series");
    expect(guide.textContent).toContain("April/May 2004");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});

describe("chart data boundary", () => {
  it("rejects global scope, wrong units, duplicate facts and withheld numeric values", () => {
    expect(() => parseContracts({ ...contracts(8), scope: "global" }, 8)).toThrow();
    const badUnit = contracts(8); badUnit.points[0].unit = QUANTITY_UNIT;
    expect(() => parseContracts(badUnit, 8)).toThrow();
    const duplicate = contracts(8); duplicate.points.push(duplicate.points[0]);
    expect(() => parseContracts(duplicate, 8)).toThrow();
    const withheld = contracts(9); withheld.points[0].value_status = "withheld";
    expect(() => parseContracts(withheld, 9)).toThrow();
  });
  it("rejects non-mock prices and mismatched spot/term periods", () => {
    const nonMock = structuredClone(prices); (nonMock.series[0].provenance as { data_status: string }).data_status = "observed";
    expect(() => parsePrices(nonMock)).toThrow();
    const mismatch = structuredClone(prices); mismatch.series[0].points.pop();
    expect(() => parsePrices(mismatch)).toThrow();
  });
  it("filters supplier, material and reporting vintage without mixing quantities and prices", () => {
    const data = contracts(10);
    const older = data.points.map(point => ({ ...point, report_year: 2024 }));
    data.points.push(...older);
    const selected = selectContractPoints(data, 10, { year: "2025", supplier: "us", material: "total", measure: "quantity", contract: "total" });
    expect(selected.length).toBeGreaterThan(0);
    expect(selected.every(point => point.report_year === 2025 && point.supplier_scope === "us" && point.unit === QUANTITY_UNIT)).toBe(true);
  });
});
