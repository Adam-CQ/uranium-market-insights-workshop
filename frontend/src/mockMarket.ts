export interface UraniumPricePoint {
  month: string;
  spot: number;
  longTerm: number;
}

// Invented teaching values; not Cameco observations or EIA statistics.
export const mockPrices: UraniumPricePoint[] = [
  { month: "2025-01", spot: 70, longTerm: 80 },
  { month: "2025-02", spot: 68, longTerm: 80 },
  { month: "2025-03", spot: 72, longTerm: 81 },
  { month: "2025-04", spot: 74, longTerm: 81 },
  { month: "2025-05", spot: 71, longTerm: 82 },
  { month: "2025-06", spot: 76, longTerm: 83 },
];

export const mockContracting = {
  reportingYear: 2024,
  contractCount: 12,
  scope: "U.S. civilian reactor owners/operators",
};

export type PriceRange = "all" | "3m";

export function selectPrices(points: UraniumPricePoint[], range: PriceRange) {
  return range === "3m" ? points.slice(-3) : points;
}
