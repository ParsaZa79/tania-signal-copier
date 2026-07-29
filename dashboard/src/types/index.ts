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
  leverage?: number;
  currency?: string;
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
  price_open: number | null;
  price_close: number;
  sl: number | null;
  tp: number | null;
  profit: number;
  swap: number;
  commission: number;
  opened_at: string;
  closed_at: string;
  source: string;
}

// WebSocket message types
export interface WebSocketMessage {
  type: "update" | "error";
  timestamp: string;
  account_id?: string;
  positions?: Position[];
  account?: AccountInfo | null;
  connection?: {
    status: "connected" | "degraded" | "disconnected";
    stale: boolean;
    last_success_at: string | null;
  };
  error?: string;
}

// API response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Health check types
export interface MT5Health {
  connected: boolean;
  ping_ok?: boolean;
  account_accessible?: boolean;
  trading_enabled?: boolean;
  account_balance?: number;
  error?: string;
}

export interface HealthStatus {
  status: "healthy" | "unhealthy";
  mt5?: MT5Health;
}

export interface MT5ConnectResponse {
  success: boolean;
  connected: boolean;
  health: MT5Health;
  error?: string | null;
}

// Beginner-first copy-trading marketplace
export type CopyTradeAction = "open" | "modify" | "reduce" | "close";
export type CopyRiskPreset = "conservative" | "balanced" | "custom";
export type CopyTradingMode = "paper" | "live";
export type CopySubscriptionStatus = "draft" | "active" | "paused" | "stopping" | "stopped";

export interface CopyTraderStatistics {
  return_90d_pct: number | null;
  max_drawdown_pct: number | null;
  track_record_days: number;
  trade_count: number;
  follower_count: number;
  data_source: "connected_mt5";
}

export interface CopyTrader {
  id: string;
  account_id: string;
  owner_user_id: string;
  display_name: string;
  description: string;
  is_copyable: boolean;
  markets: string[];
  statistics: CopyTraderStatistics;
  stats_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CopyAccount {
  id: string;
  legacy_id: string;
  name: string;
  status: "pending_setup" | "active" | "disabled";
  setup_complete: boolean;
}

export interface CopyRiskPolicy {
  id: string;
  account_id: string;
  preset: CopyRiskPreset;
  risk_per_trade_pct: number;
  daily_loss_limit_pct: number;
  total_open_risk_pct: number;
  max_open_trades: number;
  require_stop_loss: boolean;
  allowed_symbols: string[];
  updated_at: string;
}

export interface CopySubscription {
  id: string;
  trader_id: string;
  trader_name: string | null;
  trader_markets: string[];
  follower_account_id: string;
  follower_user_id: string;
  mode: CopyTradingMode;
  status: CopySubscriptionStatus;
  risk_preset: CopyRiskPreset;
  overlap_acknowledged: boolean;
  country_code: string | null;
  disclosure_version: string | null;
  live_activated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CopyRuntimeSummary {
  account_id: string;
  status: "offline" | "starting" | "healthy" | "degraded";
  broker_server?: string | null;
  trading_enabled?: boolean;
  last_heartbeat_at?: string | null;
}

export interface CopyOverview {
  success: boolean;
  accounts: CopyAccount[];
  owned_traders: CopyTrader[];
  subscriptions: CopySubscription[];
  recent_executions: Array<{
    id: string;
    trader_name: string;
    symbol: string;
    action: CopyTradeAction;
    mode: CopyTradingMode;
    status: string;
    desired_volume: number | null;
    actual_volume: number | null;
    blocked_reason: string | null;
    target_ticket: string | null;
    created_at: string;
  }>;
  runtimes: CopyRuntimeSummary[];
  live: {
    feature_enabled: boolean;
    requires_country_eligibility: boolean;
  };
}
