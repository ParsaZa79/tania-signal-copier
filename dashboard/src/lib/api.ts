import { REST_API_URL } from "./constants";
import {
  getActiveAccountId,
  type AuthSession,
  type DashboardAccount,
} from "./auth-storage";
import type { BrokerServerOption } from "./broker-servers";
import type {
  Position,
  AccountInfo,
  HealthStatus,
  PlaceOrderRequest,
  PendingOrder,
  TradeHistoryEntry,
  MT5ConnectResponse,
  CopyOverview,
  CopyRiskPolicy,
  CopyRiskPreset,
  CopySubscription,
  CopyTrader,
  CopyTradingMode,
} from "@/types";
import { apiErrorFromResponse } from "./api-error";

export function toBrokerSymbol(symbol: string): string {
  const trimmed = symbol.trim();
  const normalized = trimmed.toUpperCase();
  if (!normalized) {
    return normalized;
  }
  if (normalized === "BTCUSD") {
    return normalized;
  }
  return normalized.endsWith("B")
    ? `${normalized.slice(0, -1)}b`
    : `${normalized}b`;
}

/**
 * Fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const headers = new Headers(options?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const accountId = getActiveAccountId();
  if (accountId) {
    headers.set("X-Account-Id", accountId);
  }

  const response = await fetch(`${REST_API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  return response.json();
}

export const AUTH_SESSION_ENDPOINT = "/api/access/session";

export async function getMe(accessToken: string): Promise<AuthSession> {
  const response = await fetchApi<{
    user: AuthSession["user"];
    accounts: DashboardAccount[];
    active_account_id: string | null;
    setup_complete?: boolean;
  }>(AUTH_SESSION_ENDPOINT, { method: "POST" });
  return {
    token: accessToken,
    user: response.user,
    accounts: response.accounts,
    activeAccountId: response.active_account_id,
    setupComplete: Boolean(response.setup_complete),
  };
}

export async function getAccounts(): Promise<{
  success: boolean;
  accounts: DashboardAccount[];
  active_account_id: string | null;
  setup_complete: boolean;
}> {
  return fetchApi("/api/accounts");
}

export async function createAccount(name: string): Promise<{
  success: boolean;
  account: DashboardAccount;
  accounts: DashboardAccount[];
  active_account_id?: string | null;
}> {
  return fetchApi("/api/accounts", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function activateAccount(accountId: string): Promise<{
  success: boolean;
  account: DashboardAccount;
  active_account_id: string | null;
  accounts: DashboardAccount[];
  runtime: {
    success: boolean;
    connected: boolean;
    error?: string | null;
  };
}> {
  return fetchApi(`/api/accounts/${encodeURIComponent(accountId)}/active`, {
    method: "PUT",
  });
}

export interface AccountSetupStatus {
  account: DashboardAccount;
  setup_complete: boolean;
  broker_configured: boolean;
  missing_fields: string[];
}

export async function getAccountSetupStatus(): Promise<{
  success: boolean;
  setup_complete: boolean;
  needs_account: boolean;
  active_account_id: string | null;
  accounts: DashboardAccount[];
  account_statuses: AccountSetupStatus[];
}> {
  return fetchApi("/api/accounts/setup-status");
}

export async function completeAccountSetup(): Promise<{
  success: boolean;
  account_status: AccountSetupStatus;
  setup: {
    setup_complete: boolean;
    active_account_id: string | null;
    accounts: DashboardAccount[];
    account_statuses: AccountSetupStatus[];
  };
}> {
  return fetchApi("/api/accounts/setup-complete", { method: "POST" });
}

export interface AccessMember {
  id: string;
  workos_user_id?: string | null;
  email: string;
  role: "owner" | "admin" | "trader" | "viewer";
  status: "active" | "disabled" | "pending";
  active_account_id?: string | null;
  invited_by?: string | null;
  invitation_id?: string | null;
  invitation_status?: string | null;
  created_at?: string;
  updated_at?: string;
  last_seen_at?: string;
}

export async function getAccessMembers(): Promise<{
  success: boolean;
  members: AccessMember[];
  roles: AccessMember["role"][];
  workos: { enabled: boolean; invitations_enabled: boolean };
}> {
  return fetchApi("/api/access");
}

export async function inviteAccessMember(
  email: string,
  role: AccessMember["role"]
): Promise<{ success: boolean; member: AccessMember; members: AccessMember[] }> {
  return fetchApi("/api/access/members", {
    method: "POST",
    body: JSON.stringify({
      email,
      role,
    }),
  });
}

export async function updateAccessMember(
  memberId: string,
  update: { role?: AccessMember["role"]; status?: AccessMember["status"] }
): Promise<{ success: boolean; member: AccessMember; members: AccessMember[] }> {
  return fetchApi(`/api/access/members/${encodeURIComponent(memberId)}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function deleteAccessMember(
  memberId: string
): Promise<{ success: boolean; members: AccessMember[] }> {
  return fetchApi(`/api/access/members/${encodeURIComponent(memberId)}`, {
    method: "DELETE",
  });
}

// Health
export const MT5_HEALTH_ENDPOINT = "/api/health/mt5";

export async function getHealth(): Promise<HealthStatus> {
  return fetchApi(MT5_HEALTH_ENDPOINT);
}

export async function connectMT5(
  config: Record<string, string>
): Promise<MT5ConnectResponse> {
  const dockerPort = config.MT5_DOCKER_PORT?.trim();
  return fetchApi("/api/mt5/connect", {
    method: "POST",
    body: JSON.stringify({
      login: config.MT5_LOGIN ? Number(config.MT5_LOGIN) : undefined,
      password: config.MT5_PASSWORD || undefined,
      server: config.MT5_SERVER || undefined,
      docker_host: config.MT5_DOCKER_HOST || undefined,
      docker_port: dockerPort ? Number(dockerPort) : undefined,
      path: config.MT5_PATH || undefined,
    }),
  });
}

export interface MT5BrokerServersPage {
  success: boolean;
  brokers: BrokerServerOption[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export async function getMT5BrokerServers({
  page = 1,
  pageSize = 8,
  query = "",
}: {
  page?: number;
  pageSize?: number;
  query?: string;
} = {}): Promise<MT5BrokerServersPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const normalizedQuery = query.trim();
  if (normalizedQuery) params.set("query", normalizedQuery);
  return fetchApi(`/api/mt5/brokers?${params.toString()}`);
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

export interface SymbolTradingInfo {
  symbol: string;
  digits: number;
  point: number;
  volume_min: number;
  volume_max: number;
  volume_step: number;
  trade_tick_value: number;
  visible: boolean;
}

export async function getSymbols(): Promise<SymbolListItem[]> {
  return fetchApi("/api/symbols");
}

export async function getSymbolInfo(
  symbol: string
): Promise<SymbolTradingInfo> {
  return fetchApi(`/api/symbols/${toBrokerSymbol(symbol)}/info`);
}

export async function getSymbolPrice(
  symbol: string
): Promise<{
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  daily_open?: number | null;
  daily_high?: number | null;
  daily_low?: number | null;
  daily_change_percent?: number | null;
}> {
  return fetchApi(`/api/symbols/${toBrokerSymbol(symbol)}/price`);
}

// Account-scoped MT5 runtime configuration
export async function getAccountRuntimeConfig(): Promise<{
  success: boolean;
  account_id: string;
  config: Record<string, string>;
  configuredSecrets: string[];
  secretFields: string[];
}> {
  return fetchApi("/api/config");
}

export async function saveAccountRuntimeConfig(
  config: Record<string, string>,
  writeEnv = false
): Promise<{ success: boolean; configuredSecrets?: string[] }> {
  return fetchApi("/api/config", {
    method: "PUT",
    body: JSON.stringify({ config, write_env: writeEnv }),
  });
}

// Beginner-first copy-trading marketplace
export async function getCopyDirectory(input?: {
  search?: string;
  market?: string;
}): Promise<{ success: boolean; traders: CopyTrader[]; ranking: "neutral" }> {
  const query = new URLSearchParams();
  if (input?.search) query.set("search", input.search);
  if (input?.market) query.set("market", input.market);
  const suffix = query.size ? `?${query.toString()}` : "";
  return fetchApi(`/api/copy/directory${suffix}`);
}

export async function getCopyOverview(): Promise<CopyOverview> {
  return fetchApi("/api/copy/overview");
}

export async function saveCopyTrader(input: {
  account_id: string;
  display_name: string;
  description: string;
  is_copyable: boolean;
}): Promise<{ success: boolean; trader: CopyTrader }> {
  return fetchApi("/api/copy/traders", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateCopyTrader(
  traderId: string,
  input: Partial<Pick<CopyTrader, "display_name" | "description" | "is_copyable">>
): Promise<{ success: boolean; trader: CopyTrader }> {
  return fetchApi(`/api/copy/traders/${encodeURIComponent(traderId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function getCopyRiskPolicy(
  accountId: string
): Promise<{ success: boolean; risk_policy: CopyRiskPolicy }> {
  return fetchApi(`/api/copy/accounts/${encodeURIComponent(accountId)}/risk-policy`);
}

export async function saveCopyRiskPolicy(
  accountId: string,
  input: {
    preset: CopyRiskPreset;
    risk_per_trade_pct?: number;
    daily_loss_limit_pct?: number;
    total_open_risk_pct?: number;
    max_open_trades?: number;
    require_stop_loss?: boolean;
    allowed_symbols?: string[];
  }
): Promise<{ success: boolean; risk_policy: CopyRiskPolicy }> {
  return fetchApi(`/api/copy/accounts/${encodeURIComponent(accountId)}/risk-policy`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function createCopySubscription(input: {
  trader_id: string;
  follower_account_id: string;
  mode: CopyTradingMode;
  risk_preset: CopyRiskPreset;
  overlap_acknowledged: boolean;
  country_code?: string;
  disclosure_version?: string;
}): Promise<{ success: boolean; subscription: CopySubscription }> {
  return fetchApi("/api/copy/subscriptions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateCopySubscription(
  subscriptionId: string,
  input: Partial<
    Pick<CopySubscription, "status" | "risk_preset" | "overlap_acknowledged">
  >
): Promise<{ success: boolean; subscription: CopySubscription }> {
  return fetchApi(`/api/copy/subscriptions/${encodeURIComponent(subscriptionId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function activateLiveCopySubscription(
  subscriptionId: string,
  input: {
    country_code: string;
    disclosure_version: string;
    checklist: Record<string, boolean>;
  }
): Promise<{ success: boolean; subscription: CopySubscription }> {
  return fetchApi(
    `/api/copy/subscriptions/${encodeURIComponent(subscriptionId)}/activate-live`,
    {
      method: "POST",
      body: JSON.stringify(input),
    }
  );
}
