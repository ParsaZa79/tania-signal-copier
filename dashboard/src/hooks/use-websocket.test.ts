import { describe, expect, it } from "vitest";
import type { AccountInfo } from "@/types";
import {
  reduceWebSocketFeedState,
  type WebSocketFeedState,
} from "./use-websocket";

const account: AccountInfo = {
  balance: 2500,
  equity: 2475,
  margin: 100,
  free_margin: 2375,
  profit: -25,
};

const emptyState: WebSocketFeedState = {
  positions: [],
  account: null,
  isConnected: false,
  hasSnapshot: false,
  error: null,
};

describe("reduceWebSocketFeedState", () => {
  it("does not treat an open browser socket as an MT5 account connection", () => {
    const state = reduceWebSocketFeedState(emptyState, { type: "socket-open" });

    expect(state.isConnected).toBe(false);
    expect(state.account).toBeNull();
    expect(state.hasSnapshot).toBe(false);
  });

  it("records a snapshot even when the backend reports MT5 as disconnected", () => {
    const state = reduceWebSocketFeedState(emptyState, {
      type: "update",
      message: {
        type: "update",
        timestamp: "2026-07-21T00:00:00Z",
        account: null,
        connection: {
          status: "disconnected",
          stale: false,
          last_success_at: null,
        },
      },
    });

    expect(state.account).toBeNull();
    expect(state.hasSnapshot).toBe(true);
  });

  it("connects only after receiving a valid account snapshot", () => {
    const state = reduceWebSocketFeedState(emptyState, {
      type: "update",
      message: {
        type: "update",
        timestamp: "2026-07-21T00:00:00Z",
        account,
        connection: {
          status: "connected",
          stale: false,
          last_success_at: "2026-07-21T00:00:00Z",
        },
      },
    });

    expect(state.isConnected).toBe(true);
    expect(state.account).toEqual(account);
  });

  it("keeps the last valid account during a transient degraded update", () => {
    const connectedState = { ...emptyState, account, isConnected: true };
    const state = reduceWebSocketFeedState(connectedState, {
      type: "update",
      message: {
        type: "update",
        timestamp: "2026-07-21T00:00:01Z",
        account: null,
        connection: {
          status: "degraded",
          stale: true,
          last_success_at: "2026-07-21T00:00:00Z",
        },
      },
    });

    expect(state.isConnected).toBe(true);
    expect(state.account).toEqual(account);
  });

  it("clears account data only after an explicit disconnect", () => {
    const connectedState = { ...emptyState, account, isConnected: true };
    const state = reduceWebSocketFeedState(connectedState, {
      type: "update",
      message: {
        type: "update",
        timestamp: "2026-07-21T00:00:20Z",
        account: null,
        connection: {
          status: "disconnected",
          stale: false,
          last_success_at: null,
        },
      },
    });

    expect(state.isConnected).toBe(false);
    expect(state.account).toBeNull();
  });
});
