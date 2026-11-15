// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { Dashboard } from "./Dashboard";

afterEach(cleanup);

describe("mock dashboard", () => {
  it("labels synthetic values, units, scope, and unavailable freshness", () => {
    render(<Dashboard />);
    expect(screen.getByRole("complementary", { name: "Mock data notice" }).textContent).toContain("all market values are invented");
    const snapshot = screen.getByRole("region", { name: "Market snapshot" });
    expect(within(snapshot).getByText("76.00 USD/lb U3O8")).toBeTruthy();
    expect(within(snapshot).getByText("83.00 USD/lb U3O8")).toBeTruthy();
    expect(within(snapshot).getByText(/U.S. civilian reactor owners\/operators/).textContent).toContain("2024");
    expect(within(snapshot).getByText("No source retrieved")).toBeTruthy();
    expect(within(snapshot).getAllByText("Mock data")).toHaveLength(4);
  });

  it("filters chart and table together and updates snapshot comparisons", () => {
    render(<Dashboard />);
    const table = screen.getByRole("table", { name: "Mock price values — USD per pound U3O8" });
    expect(within(table).getAllByRole("row")).toHaveLength(7);
    expect(screen.getByText(/\+6.00 USD\/lb U3O8 since 2025-01/)).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Time range" }), { target: { value: "3m" } });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).queryByText("2025-01")).toBeNull();
    expect(within(table).getByText("2025-04")).toBeTruthy();
    expect(screen.getAllByText(/\+2.00 USD\/lb U3O8 since 2025-04/)).toHaveLength(2);
    expect(screen.getByRole("img", { name: "Mock uranium price history" }).textContent).not.toContain("2025-01");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "all" } });
    expect(within(table).getAllByRole("row")).toHaveLength(7);
  });
});
