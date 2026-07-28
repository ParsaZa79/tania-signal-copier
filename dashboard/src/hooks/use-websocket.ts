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
      return { ...state, isConnected: false, error: null };
    case "socket-closed":
      return { ...state, isConnected: false };
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
}: UseWebSocketOptions): UseWebSocketReturn {
  const [feed, dispatch] = useReducer(reduceWebSocketFeedState, initialFeedState);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const connectionEnabledRef = useRef(false);
  const maxReconnectAttempts = 10;
  const connectRef = useRef<() => void>(() => {});

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled || !token || !accountId || !connectionEnabledRef.current) return;

    clearReconnectTimer();
    const previousSocket = wsRef.current;
    wsRef.current = null;
    detachAndClose(previousSocket);

    try {
      const ws = new WebSocket(buildAuthenticatedWsUrl(WS_URL, token, accountId));
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        console.log("WebSocket connected");
        dispatch({ type: "socket-open" });
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return;
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
        dispatch({ type: "socket-closed" });
        console.log("WebSocket disconnected");

        if (!connectionEnabledRef.current) return;
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
          console.log(`Reconnecting in ${delay}ms...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current += 1;
            connectRef.current();
          }, delay);
        } else {
          dispatch({ type: "error", message: "Max reconnection attempts reached" });
        }
      };
    } catch (creationError) {
      dispatch({ type: "error", message: "Failed to create WebSocket connection" });
      console.error("WebSocket creation error:", creationError);
    }
  }, [accountId, clearReconnectTimer, enabled, token]);

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
    connectRef.current();
  }, []);

  useEffect(() => {
    connectionEnabledRef.current = enabled && Boolean(token) && Boolean(accountId);
    if (!connectionEnabledRef.current) return;

    connectRef.current();

    return () => {
      connectionEnabledRef.current = false;
      clearReconnectTimer();
      const socket = wsRef.current;
      wsRef.current = null;
      detachAndClose(socket);
    };
  }, [accountId, clearReconnectTimer, enabled, token]);

  return { ...feed, reconnect };
}
