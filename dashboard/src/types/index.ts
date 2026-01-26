// Position types
export interface Position {
  ticket: number;
  symbol: string;
  type: "buy" | "sell";
  volume: number;
  price_open: number;
  price_current: number | null;
  sl: number;
  tp: number;
  profit: number;
  swap: number;
  time: number | null;
}

// Account types
export interface AccountInfo {
  balance: number;
  equity: number;
  margin: number;
  free_margin: number;
  profit: number;
}

// Order types
export type OrderType =
  | "buy"
  | "sell"
  | "buy_limit"
  | "sell_limit"
  | "buy_stop"
  | "sell_stop";

export interface PlaceOrderRequest {
  symbol: string;
  order_type: OrderType;
  volume: number;
  price?: number;
  sl?: number;
  tp?: number;
  comment?: string;
}

export interface PendingOrder {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  price_open: number;
  sl: number;
  tp: number;
  comment: string;
}

// Trade history types
export interface TradeHistoryEntry {
  id: number;
  ticket: number;
  symbol: string;
  order_type: string;
  volume: number;
  price_open: number;
  price_close: number;
  sl: number | null;
  tp: number | null;
  profit: number;
  swap: number;
  commission: number;
  opened_at: string;
  closed_at: string;
  source: string;
  telegram_msg_id: number | null;
}

// WebSocket message types
export interface WebSocketMessage {
  type: "update" | "error";
  timestamp: string;
  positions?: Position[];
  account?: AccountInfo;
  error?: string;
}

// API response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Health check types
export interface HealthStatus {
  status: "healthy" | "unhealthy";
  mt5: {
    connected: boolean;
    ping_ok?: boolean;
    account_accessible?: boolean;
    trading_enabled?: boolean;
    account_balance?: number;
    error?: string;
  };
}
