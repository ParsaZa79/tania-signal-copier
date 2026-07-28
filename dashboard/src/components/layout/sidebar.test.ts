import { describe, expect, it } from "vitest";

import { isNavigationPathActive } from "./sidebar";

describe("mobile navigation route matching", () => {
  it("matches exact and nested destinations", () => {
    expect(isNavigationPathActive("/", "/")).toBe(true);
    expect(isNavigationPathActive("/copy-trading/trader-42", "/copy-trading")).toBe(true);
    expect(isNavigationPathActive("/orders", "/orders")).toBe(true);
  });

  it("does not highlight routes that only share a prefix", () => {
    expect(isNavigationPathActive("/history-archive", "/history")).toBe(false);
    expect(isNavigationPathActive("/settings-old", "/settings")).toBe(false);
    expect(isNavigationPathActive("/orders", "/")).toBe(false);
  });
});
