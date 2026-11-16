import { expect, test } from "@playwright/test";
import { contracts, fixtureForUrl } from "../test/fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", route => route.fulfill({ json: fixtureForUrl(route.request().url()) }));
});

test("real charts render, controls update tables, and signings retain U.S. scope", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("22 contracts", { exact: true })).toBeVisible();
  await expect(page.locator(".market-chart svg")).toHaveCount(2);
  const price = page.getByRole("region", { name: "Uranium price history — mock data" });
  await price.getByLabel("Time range").selectOption("3m");
  await expect(price.getByRole("table").getByRole("row")).toHaveCount(4);
  await expect(price.getByRole("cell", { name: "2025-01", exact: true })).toHaveCount(0);
  const eia = page.getByRole("region", { name: "U.S. utility contracting and deliveries — EIA" });
  await expect(eia.getByText("U.S. civilian reactor owners/operators", { exact: true })).toBeVisible();
  await expect(eia.getByText(/Unit: contracts/)).toBeVisible();
  await eia.getByLabel("Measure", { exact: true }).selectOption("quantity");
  await expect(eia.getByText(/Unit: thousand lb U3O8 equivalent/)).toBeVisible();
  await expect(eia.getByRole("table").getByRole("cell", { name: "4,321", exact: true })).toBeVisible();
  await expect(eia.getByRole("link", { name: "U.S. Energy Information Administration — Table 8" })).toHaveAttribute("href", "https://www.eia.gov/uranium/marketing/table8.php");
  const chart = page.locator(".market-chart").nth(1);
  const bounds = (await chart.boundingBox())!;
  await chart.hover({ position: { x: bounds.width / 2, y: 150 } });
  await expect(chart).toContainText("EIA Table 8");
  await expect(chart).toContainText("Published 2026-08-13");
  await eia.getByText("Source details", { exact: true }).first().click();
  await expect(eia.getByText("offline-test-vintage-2025", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("future totals and withheld rows are distinct; supplier and material views stay separate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("22 contracts", { exact: true })).toBeVisible();
  const eia = page.getByRole("region", { name: "U.S. utility contracting and deliveries — EIA" });
  await eia.getByLabel("Contracting view").selectOption("9");
  await expect(eia.getByLabel("Reporting year")).toHaveValue("2025");
  await expect(eia.getByText("Withheld (W)", { exact: true }).first()).toBeVisible();
  await expect(eia.getByText(/Published totals \(not plotted with components\)/)).toBeVisible();
  await eia.getByLabel("Contracting view").selectOption("10");
  await eia.getByLabel("Supplier scope").selectOption("us");
  await expect(eia.getByText(/All plotted component values are withheld/)).toBeVisible();
  await expect(eia.getByText(/Published totals \(not plotted with components\)/)).toContainText("1,317");
  await eia.getByLabel("Contracting view").selectOption("7");
  await eia.getByLabel("Material", { exact: true }).selectOption("natural_uf6");
  await expect(eia.getByText(/All plotted component values are withheld/)).toBeVisible();
  await expect(eia.getByRole("heading", { name: /Actual deliveries with reported price/ })).toBeVisible();
});

test("source guide is accessible and page does not overflow at its viewport", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("22 contracts", { exact: true })).toBeVisible();
  const guide = page.locator("details").filter({ has: page.locator("summary", { hasText: "Check Cameco prices manually" }) });
  await guide.locator("summary").click();
  await expect(guide.getByRole("link", { name: "Cameco — Uranium Price", exact: true })).toHaveAttribute("href", "https://www.cameco.com/invest/markets/uranium-price");
  await expect(guide.getByText(/does not import, refresh, or validate our mock series/)).toBeVisible();
  await expect(guide.getByText(/April\/May 2004/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const chart = page.locator(".market-chart").first();
  expect((await chart.boundingBox())!.width).toBeGreaterThan(200);
  await page.screenshot({ path: testInfo.outputPath("dashboard.png"), fullPage: true });
});

test("HTTP failure shows retry instead of mock EIA fallback", async ({ page }) => {
  await page.route("**/api/v1/contracts/signings?*", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("HTTP 503");
  await expect(page.getByText("22 contracts", { exact: true })).toHaveCount(0);
  await page.route("**/api/v1/contracts/signings?*", route => route.fulfill({ json: contracts(8) }));
  await page.getByRole("button", { name: "Retry data request" }).click();
  await expect(page.getByText("22 contracts", { exact: true })).toBeVisible();
});
