"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { WS_URL } from "@/lib/constants";
import { buildAuthenticatedWsUrl } from "@/lib/auth-storage";
import type { Position, AccountInfo, WebSocketMessage } from "@/types";

interface UseWebSocketReturn {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  hasSnapshot: boolean;
  error: string | null;
  reconnect: () => void;
}

interface UseWebSocketOptions {
  enabled: boolean;
  token: string;
  accountId: string | null;
  getAccessToken?: () => Promise<string | undefined>;
}

const MAX_RECONNECT_DELAY_MS = 30_000;
const HEARTBEAT_INTERVAL_MS = 20_000;
const STALE_CONNECTION_MS = 45_000;

export function webSocketReconnectDelay(attempt: number): number {
  return Math.min(1000 * 2 ** Math.max(0, attempt), MAX_RECONNECT_DELAY_MS);
}

export function isWebSocketConnectionStale(
  lastMessageAt: number,
  now = Date.now()
): boolean {
  return lastMessageAt > 0 && now - lastMessageAt >= STALE_CONNECTION_MS;
}

export async function resolveWebSocketAccessToken(
  fallbackToken: string,
  getAccessToken?: () => Promise<string | undefined>
): Promise<string | undefined> {
  return getAccessToken ? getAccessToken() : fallbackToken;
}

export interface WebSocketFeedState {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  /**
   * True once the backend has reported on the account at least once. Until
   * then a null account means "not heard back yet" rather than "MT5 is down",
   * which lets the UI show a loader instead of a disconnected state.
   */
  hasSnapshot: boolean;
  error: string | null;
}

export type WebSocketFeedAction =
  | { type: "reset" }
  | { type: "socket-open" }
  | { type: "socket-closed" }
  | { type: "update"; message: WebSocketMessage }
  | { type: "error"; message: string };

const initialFeedState: WebSocketFeedState = {
  positions: [],
  account: null,
  isConnected: false,
  hasSnapshot: false,
  error: null,
};

export function reduceWebSocketFeedState(
  state: WebSocketFeedState,
  action: WebSocketFeedAction
): WebSocketFeedState {
  switch (action.type) {
    case "reset":
      return initialFeedState;
    case "socket-open":
      // A browser socket only proves that the API is reachable. The account is
      // connected only after the backend sends a valid MT5 account snapshot.
      // Preserve an existing MT5 snapshot while the transport reconnects.
      return { ...state, error: null };
    case "socket-closed":
      // Losing the browser transport does not mean MT5 disconnected. Keep the
      // last explicit backend status until a fresh snapshot replaces it.
      return state;
    case "error":
      return { ...state, error: action.message };
    case "update": {
      const { message } = action;
      const status = message.connection?.status;
      const positions = message.positions ?? state.positions;
      let account = state.account;

      if (message.account) {
        account = message.account;
      } else if (status === "disconnected" || !message.connection) {
        account = null;
      }

      if (status === "connected") {
        return {
          positions,
          account,
          isConnected: account !== null,
          hasSnapshot: true,
          error: null,
        };
      }
      if (status === "degraded") {
        return {
          ...state,
          positions,
          account,
          isConnected: account !== null,
          hasSnapshot: true,
        };
      }
      if (status === "disconnected") {
        return {
          ...state,
          positions,
          account: null,
          isConnected: false,
          hasSnapshot: true,
        };
      }

      // Backwards compatibility for servers that predate explicit status.
      return {
        ...state,
        positions,
        account,
        isConnected: message.account != null,
        hasSnapshot: true,
      };
    }
  }
}

function detachAndClose(socket: WebSocket | null) {
  if (!socket) return;
  socket.onopen = null;
  socket.onmessage = null;
  socket.onerror = null;
  socket.onclose = null;
  socket.close();
}

export function useWebSocket({
  enabled,
  token,
  accountId,
  getAccessToken,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [feed, dispatch] = useReducer(reduceWebSocketFeedState, initialFeedState);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttempts = useRef(0);
  const connectionGenerationRef = useRef(0);
  const connectionEnabledRef = useRef(false);
  const lastMessageAtRef = useRef(0);
  const connectRef = useRef<() => Promise<void>>(async () => {});

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!connectionEnabledRef.current || reconnectTimeoutRef.current) return;

    const delay = webSocketReconnectDelay(reconnectAttempts.current);
    reconnectAttempts.current += 1;
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null;
      void connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(async () => {
    if (!enabled || !token || !accountId || !connectionEnabledRef.current) return;

    clearReconnectTimer();
    clearHeartbeat();
    const generation = ++connectionGenerationRef.current;
    const previousSocket = wsRef.current;
    wsRef.current = null;
    detachAndClose(previousSocket);

    try {
      const freshToken = await resolveWebSocketAccessToken(token, getAccessToken);
      if (
        generation !== connectionGenerationRef.current ||
        !connectionEnabledRef.current
      ) {
        return;
      }
      if (!freshToken) {
        throw new Error("A fresh access token is unavailable");
      }

      const ws = new WebSocket(
        buildAuthenticatedWsUrl(WS_URL, freshToken, accountId)
      );
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        console.log("WebSocket connected");
        dispatch({ type: "socket-open" });
        reconnectAttempts.current = 0;
        lastMessageAtRef.current = Date.now();
        clearHeartbeat();
        heartbeatIntervalRef.current = setInterval(() => {
          if (wsRef.current !== ws) {
            clearHeartbeat();
            return;
          }
          if (
            ws.readyState !== WebSocket.OPEN ||
            isWebSocketConnectionStale(lastMessageAtRef.current)
          ) {
            ws.close();
            return;
          }
          ws.send("ping");
        }, HEARTBEAT_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return;
        lastMessageAtRef.current = Date.now();
        if (event.data === "pong") return;

        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          if (data.account_id && data.account_id !== accountId) return;

          if (data.type === "update") {
            dispatch({ type: "update", message: data });
          } else if (data.type === "error") {
            dispatch({ type: "error", message: data.error || "Unknown error" });
          }
        } catch (parseError) {
          console.error("Failed to parse WebSocket message:", parseError);
        }
      };

      ws.onerror = () => {
        if (wsRef.current !== ws) return;
        dispatch({ type: "error", message: "WebSocket connection error" });
        console.error("WebSocket error");
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        wsRef.current = null;
        clearHeartbeat();
        dispatch({ type: "socket-closed" });
        console.log("WebSocket disconnected");

        if (!connectionEnabledRef.current) return;
        scheduleReconnect();
      };
    } catch (creationError) {
      dispatch({ type: "error", message: "Failed to create WebSocket connection" });
      console.error("WebSocket creation error:", creationError);
      scheduleReconnect();
    }
  }, [
    accountId,
    clearHeartbeat,
    clearReconnectTimer,
    enabled,
    getAccessToken,
    scheduleReconnect,
    token,
  ]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    // Reset immediately on account switches so the previous account is never shown.
    dispatch({ type: "reset" });
    reconnectAttempts.current = 0;
  }, [accountId]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    clearReconnectTimer();
    void connectRef.current();
  }, [clearReconnectTimer]);

  useEffect(() => {
    connectionEnabledRef.current = enabled && Boolean(token) && Boolean(accountId);
    if (!connectionEnabledRef.current) return;

    void connectRef.current();

    return () => {
      connectionEnabledRef.current = false;
      connectionGenerationRef.current += 1;
      clearReconnectTimer();
      clearHeartbeat();
      const socket = wsRef.current;
      wsRef.current = null;
      detachAndClose(socket);
    };
  }, [accountId, clearHeartbeat, clearReconnectTimer, enabled, token]);

  useEffect(() => {
    if (!enabled || !token || !accountId) return;

    const handleWake = (event: Event) => {
      if (
        event.type === "visibilitychange" &&
        document.visibilityState !== "visible"
      ) {
        return;
      }

      reconnectAttempts.current = 0;
      clearReconnectTimer();
      const socket = wsRef.current;
      if (
        !socket ||
        socket.readyState !== WebSocket.OPEN ||
        isWebSocketConnectionStale(lastMessageAtRef.current)
      ) {
        void connectRef.current();
        return;
      }

      socket.send("ping");
    };

    document.addEventListener("visibilitychange", handleWake);
    window.addEventListener("focus", handleWake);
    window.addEventListener("online", handleWake);
    window.addEventListener("pageshow", handleWake);

    return () => {
      document.removeEventListener("visibilitychange", handleWake);
      window.removeEventListener("focus", handleWake);
      window.removeEventListener("online", handleWake);
      window.removeEventListener("pageshow", handleWake);
    };
  }, [accountId, clearReconnectTimer, enabled, token]);

  return { ...feed, reconnect };
}
