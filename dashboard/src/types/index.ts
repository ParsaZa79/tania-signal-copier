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

// Bot Configuration types
export interface BotConfig {
  // Telegram settings
  TELEGRAM_API_ID: string;
  TELEGRAM_API_HASH: string;
  TELEGRAM_CHANNEL: string;
  // MT5 settings
  MT5_LOGIN: string;
  MT5_PASSWORD: string;
  MT5_SERVER: string;
  MT5_PATH?: string; // Windows only
  MT5_DOCKER_HOST?: string; // macOS/Linux
  MT5_DOCKER_PORT?: string; // macOS/Linux
  // Trading settings
  DEFAULT_LOT_SIZE: string;
  MAX_RISK_PERCENT: string;
  SCALP_LOT_SIZE: string;
  RUNNER_LOT_SIZE: string;
  TRADING_STRATEGY: "dual_tp" | "single";
  EDIT_WINDOW_SECONDS: string;
  // Optional
  TEST_SYMBOL?: string;
}

export interface Preset {
  name: string;
  created_at: string;
  modified_at: string;
  values: Partial<BotConfig>;
}

export interface TelegramChannel {
  id: string;
  name: string;
  username?: string;
  type: "channel" | "group";
}

export type BotStatus = "stopped" | "starting" | "running" | "stopping" | "error";

export interface BotState {
  status: BotStatus;
  pid?: number;
  started_at?: string;
  error?: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error" | "bot" | "analysis";
  message: string;
}

export interface AnalysisSummary {
  total_signals: number;
  tp2_hit: number;
  tp1_hit: number;
  sl_hit: number;
  tp_unnumbered: number;
  win_rate: number;
  tp1_to_tp2_conversion: number;
  date_range: {
    start: string;
    end: string;
  } | null;
  avg_time_to_tp1_minutes?: number;
  avg_time_to_tp2_minutes?: number;
}

export interface TrackedPosition {
  msg_id: number;
  mt5_ticket: number;
  symbol: string;
  role: "scalp" | "runner" | "single";
  order_type: string;
  entry_price: number | null;
  stop_loss: number | null;
  lot_size: number | null;
  status: "open" | "closed" | "pending_completion";
  opened_at: string;
}
