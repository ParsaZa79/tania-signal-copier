import { describe, expect, it } from "vitest";
import { toBrokerSymbol } from "./api";

describe("broker symbol normalization", () => {
  it("preserves the broker's lowercase suffix", () => {
    expect(toBrokerSymbol("XAUUSDb")).toBe("XAUUSDb");
    expect(toBrokerSymbol("xauusdb")).toBe("XAUUSDb");
    expect(toBrokerSymbol("XAUUSD")).toBe("XAUUSDb");
    expect(toBrokerSymbol("BTCUSD")).toBe("BTCUSD");
  });
});
