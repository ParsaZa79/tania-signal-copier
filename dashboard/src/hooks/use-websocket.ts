"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { WS_URL } from "@/lib/constants";
import type { Position, AccountInfo, WebSocketMessage } from "@/types";

interface UseWebSocketReturn {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const [positions, setPositions] = useState<Position[]>([]);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);

          if (data.type === "update") {
            if (data.positions) {
              setPositions(data.positions);
            }
            if (data.account) {
              setAccount(data.account);
            }
          } else if (data.type === "error") {
            setError(data.error || "Unknown error");
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection error");
        console.error("WebSocket error");
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log("WebSocket disconnected");

        // Attempt to reconnect with exponential backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempts.current),
            30000
          );
          console.log(`Reconnecting in ${delay}ms...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connectRef.current();
          }, delay);
        } else {
          setError("Max reconnection attempts reached");
        }
      };
    } catch (e) {
      setError("Failed to create WebSocket connection");
      console.error("WebSocket creation error:", e);
    }
  }, []);

  // Keep connectRef in sync with the latest connect function
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    // Initial connection setup - necessary to establish WebSocket on mount
    // eslint-disable-next-line react-hooks/set-state-in-effect
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { positions, account, isConnected, error, reconnect };
}
