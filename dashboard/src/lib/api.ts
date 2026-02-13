import { API_URL } from "./constants";
import type {
  Position,
  AccountInfo,
  HealthStatus,
  PlaceOrderRequest,
  PendingOrder,
  TradeHistoryEntry,
} from "@/types";

function toBrokerSymbol(symbol: string): string {
  const normalized = symbol.trim().toUpperCase();
  if (!normalized) {
    return normalized;
  }
  return normalized.endsWith("B") ? normalized : `${normalized}b`;
}

/**
 * Fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Health
export async function getHealth(): Promise<HealthStatus> {
  return fetchApi("/api/health");
}

// Positions
export async function getPositions(): Promise<Position[]> {
  return fetchApi("/api/positions");
}

export async function getPosition(ticket: number): Promise<Position> {
  return fetchApi(`/api/positions/${ticket}`);
}

export async function modifyPosition(
  ticket: number,
  sl?: number,
  tp?: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/positions/${ticket}`, {
    method: "PUT",
    body: JSON.stringify({ sl, tp }),
  });
}

export async function closePosition(
  ticket: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/positions/${ticket}`, {
    method: "DELETE",
  });
}

// Orders
export async function placeOrder(
  order: PlaceOrderRequest
): Promise<{ success: boolean; ticket?: number; error?: string }> {
  const normalizedOrder: PlaceOrderRequest = {
    ...order,
    symbol: toBrokerSymbol(order.symbol),
  };
  return fetchApi("/api/orders", {
    method: "POST",
    body: JSON.stringify(normalizedOrder),
  });
}

export async function getPendingOrders(
  symbol?: string
): Promise<PendingOrder[]> {
  const query = symbol ? `?symbol=${toBrokerSymbol(symbol)}` : "";
  return fetchApi(`/api/orders/pending${query}`);
}

export async function cancelOrder(
  ticket: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/orders/${ticket}`, {
    method: "DELETE",
  });
}

// Account
export async function getAccountInfo(): Promise<AccountInfo> {
  return fetchApi("/api/account");
}

export async function getTradeHistory(
  page: number = 1,
  pageSize: number = 50,
  symbol?: string,
  fromDate?: string,
  toDate?: string
): Promise<{ trades: TradeHistoryEntry[]; total: number }> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (symbol) params.set("symbol", toBrokerSymbol(symbol));
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  return fetchApi(`/api/account/history?${params}`);
}

// Symbols
export interface SymbolListItem {
  value: string;
  label: string;
}

export async function getSymbols(): Promise<SymbolListItem[]> {
  return fetchApi("/api/symbols");
}

export async function getSymbolPrice(
  symbol: string
): Promise<{ symbol: string; bid: number; ask: number; spread: number }> {
  return fetchApi(`/api/symbols/${toBrokerSymbol(symbol)}/price`);
}

// ============================================================
// Bot Management APIs (FastAPI backend)
// ============================================================

// Bot Config
export async function getBotConfig(): Promise<{
  success: boolean;
  config: Record<string, string>;
}> {
  return fetchApi("/api/config");
}

export async function saveBotConfig(
  config: Record<string, string>,
  writeEnv = false
): Promise<{ success: boolean }> {
  return fetchApi("/api/config", {
    method: "PUT",
    body: JSON.stringify({ config, write_env: writeEnv }),
  });
}

// Presets
export async function getPresets(): Promise<{
  success: boolean;
  presets: Array<{ name: string; created_at: string; modified_at: string }>;
  lastPreset: string | null;
}> {
  return fetchApi("/api/config/presets");
}

export async function getPreset(name: string): Promise<{
  success: boolean;
  preset: {
    name: string;
    created_at: string;
    modified_at: string;
    values: Record<string, string>;
  };
}> {
  return fetchApi(`/api/config/presets/${encodeURIComponent(name)}`);
}

export async function savePreset(
  name: string,
  values: Record<string, string>
): Promise<{ success: boolean }> {
  return fetchApi("/api/config/presets", {
    method: "POST",
    body: JSON.stringify({ name, values }),
  });
}

export async function deletePreset(name: string): Promise<{ success: boolean }> {
  return fetchApi(`/api/config/presets/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

// Bot Control
export async function getBotStatus(): Promise<{
  success: boolean;
  status: "stopped" | "starting" | "running" | "stopping" | "error";
  pid?: number;
  started_at?: string;
  error?: string;
}> {
  return fetchApi("/api/bot/status");
}

export async function startBot(options?: {
  preventSleep?: boolean;
  writeEnv?: boolean;
  config?: Record<string, string>;
}): Promise<{
  success: boolean;
  status?: string;
  pid?: number;
  error?: string;
}> {
  return fetchApi("/api/bot/start", {
    method: "POST",
    body: JSON.stringify({
      prevent_sleep: options?.preventSleep ?? false,
      write_env: options?.writeEnv ?? false,
      config: options?.config,
    }),
  });
}

export async function stopBot(): Promise<{
  success: boolean;
  status?: string;
  error?: string;
}> {
  return fetchApi("/api/bot/stop", {
    method: "POST",
  });
}

// Bot Tracked Positions
export async function getTrackedPositions(): Promise<{
  success: boolean;
  positions: Array<{
    msg_id: number;
    mt5_ticket: number;
    symbol: string;
    role: string;
    order_type: string;
    entry_price: number | null;
    stop_loss: number | null;
    lot_size: number | null;
    status: string;
    opened_at: string;
  }>;
  total: number;
  open: number;
  closed: number;
}> {
  return fetchApi("/api/bot/positions");
}

export async function clearTrackedPositions(): Promise<{ success: boolean }> {
  return fetchApi("/api/bot/positions", { method: "DELETE" });
}

// Analysis
export async function getAnalysisSummary(): Promise<{
  success: boolean;
  summary: {
    total_signals: number;
    tp2_hit: number;
    tp1_hit: number;
    sl_hit: number;
    tp_unnumbered: number;
    win_rate: number;
    tp1_to_tp2_conversion: number;
    date_range: { start: string; end: string } | null;
    avg_time_to_tp1_minutes?: number;
    avg_time_to_tp2_minutes?: number;
  };
}> {
  return fetchApi("/api/analysis/summary");
}

export async function runAnalysis(
  action: "fetch" | "report",
  options?: { total?: number; batch?: number; delay?: number }
): Promise<{
  success: boolean;
  output?: string;
  error?: string;
}> {
  return fetchApi("/api/analysis/run", {
    method: "POST",
    body: JSON.stringify({ action, ...options }),
  });
}

// Telegram Channels
export interface TelegramChannel {
  id: string;
  name: string;
  username?: string;
  type: "channel" | "group";
}

export async function getTelegramChannels(
  apiId: string,
  apiHash: string
): Promise<{ channels: TelegramChannel[] }> {
  return fetchApi(`/api/telegram/channels?api_id=${apiId}&api_hash=${apiHash}`);
}
