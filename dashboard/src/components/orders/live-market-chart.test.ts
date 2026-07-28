import { describe, expect, it } from "vitest";
import { toTradingViewSymbol } from "./live-market-chart";

describe("TradingView symbol mapping", () => {
  it("maps broker-suffixed metals and forex pairs to TradingView", () => {
    expect(toTradingViewSymbol("XAUUSDb")).toBe("OANDA:XAUUSD");
    expect(toTradingViewSymbol("EURUSDb")).toBe("OANDA:EURUSD");
  });

  it("uses suitable TradingView venues for crypto and indices", () => {
    expect(toTradingViewSymbol("BTCUSD")).toBe("BITSTAMP:BTCUSD");
    expect(toTradingViewSymbol("US500b")).toBe("OANDA:SPX500USD");
  });
});
