import { API_URL } from "./constants";
import type {
  Position,
  AccountInfo,
  HealthStatus,
  PlaceOrderRequest,
  PendingOrder,
  TradeHistoryEntry,
} from "@/types";

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
  return fetchApi("/api/orders", {
    method: "POST",
    body: JSON.stringify(order),
  });
}

export async function getPendingOrders(
  symbol?: string
): Promise<PendingOrder[]> {
  const query = symbol ? `?symbol=${symbol}` : "";
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
  if (symbol) params.set("symbol", symbol);
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
  return fetchApi(`/api/symbols/${symbol}/price`);
}
