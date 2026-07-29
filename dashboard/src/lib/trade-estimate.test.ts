import { describe, expect, it } from "vitest";

import { estimateTradeOutcome, formatSignedCurrency } from "./trade-estimate";

describe("trade outcome estimates", () => {
  const gold = {
    point: 0.01,
    tickValue: 1,
    volume: 0.01,
  };

  it("calculates sell-side stop loss and take profit in account currency", () => {
    expect(
      estimateTradeOutcome({
        ...gold,
        entryPrice: 4069,
        exitPrice: 4092,
        isBuy: false,
      })
    ).toBeCloseTo(-23);
    expect(
      estimateTradeOutcome({
        ...gold,
        entryPrice: 4069,
        exitPrice: 4028,
        isBuy: false,
      })
    ).toBeCloseTo(41);
  });

  it("keeps the direction correct for buy orders", () => {
    expect(
      estimateTradeOutcome({
        ...gold,
        entryPrice: 4069,
        exitPrice: 4059,
        isBuy: true,
      })
    ).toBeCloseTo(-10);
    expect(
      estimateTradeOutcome({
        ...gold,
        entryPrice: 4069,
        exitPrice: 4084,
        isBuy: true,
      })
    ).toBeCloseTo(15);
  });

  it("does not estimate with incomplete broker metadata", () => {
    expect(
      estimateTradeOutcome({
        ...gold,
        entryPrice: 4069,
        exitPrice: 4092,
        isBuy: false,
        tickValue: 0,
      })
    ).toBeNull();
  });

  it("formats signed dollar outcomes", () => {
    expect(formatSignedCurrency(-23)).toBe("−$23.00");
    expect(formatSignedCurrency(41)).toBe("+$41.00");
  });
});
