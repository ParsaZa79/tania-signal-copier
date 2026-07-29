import { describe, expect, it } from "vitest";
import { positionsPageTestHelpers } from "./page";

describe("positions page helpers", () => {
  it("uses friendly market names for common beginner-facing symbols", () => {
    expect(positionsPageTestHelpers.friendlyMarketName("XAUUSD.a")).toBe("Gold");
    expect(positionsPageTestHelpers.friendlyMarketName("EURUSD")).toBe("Euro / US Dollar");
    expect(positionsPageTestHelpers.friendlyMarketName("US500.cash")).toBe("S&P 500");
  });

  it("formats forex and high-value market prices at useful precision", () => {
    expect(positionsPageTestHelpers.formatPrice(1.087)).toBe("1.08700");
    expect(positionsPageTestHelpers.formatPrice(2414.5)).toBe("2414.50");
    expect(positionsPageTestHelpers.formatPrice(null)).toBe("Waiting…");
    expect(positionsPageTestHelpers.formatOptionalPrice(4028)).toBe("4028.00");
    expect(positionsPageTestHelpers.formatOptionalPrice(0)).toBe("—");
  });

  it("formats account leverage as a trading ratio", () => {
    expect(positionsPageTestHelpers.formatLeverage(100)).toBe("1:100");
    expect(positionsPageTestHelpers.formatLeverage(0)).toBe("—");
    expect(positionsPageTestHelpers.formatLeverage(undefined)).toBe("—");
  });

  it("calculates pending-order loss and profit from broker tick values", () => {
    expect(
      positionsPageTestHelpers.estimatePendingOrderOutcomes(
        {
          ticket: 199898322,
          symbol: "XAUUSDb",
          type: "sell_limit",
          volume: 0.01,
          price_open: 4069,
          sl: 4092,
          tp: 4028,
          comment: "",
        },
        {
          symbol: "XAUUSDb",
          digits: 2,
          point: 0.01,
          volume_min: 0.01,
          volume_max: 100,
          volume_step: 0.01,
          trade_tick_value: 1,
          visible: true,
        }
      )
    ).toEqual({
      potentialLoss: -23,
      potentialProfit: 41,
    });
  });

  it("shows no estimate when an order has no protection targets", () => {
    expect(
      positionsPageTestHelpers.estimatePendingOrderOutcomes(
        {
          ticket: 2001,
          symbol: "GBPUSD",
          type: "buy_limit",
          volume: 0.03,
          price_open: 1.335,
          sl: 0,
          tp: 0,
          comment: "",
        },
        {
          symbol: "GBPUSD",
          digits: 5,
          point: 0.00001,
          volume_min: 0.01,
          volume_max: 100,
          volume_step: 0.01,
          trade_tick_value: 1,
          visible: true,
        }
      )
    ).toEqual({
      potentialLoss: null,
      potentialProfit: null,
    });
  });
});
