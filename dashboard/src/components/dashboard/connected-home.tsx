"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Copy,
  Info,
  RefreshCw,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { Skeleton } from "@/components/amicro/skeleton";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { EquityChart, buildEquityCurve } from "@/components/dashboard/equity-chart";
import { getCopyOverview, getCopyRiskPolicy, getTradeHistory } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";
import type {
  AccountInfo,
  CopyOverview,
  CopyRiskPolicy,
  Position,
  TradeHistoryEntry,
} from "@/types";

interface ConnectedHomeProps {
  account: AccountInfo | null;
  accountPending?: boolean;
  accountId: string | null;
  email: string;
  isConnected: boolean;
  positions: Position[];
  preview?: boolean;
  reconnect: () => void;
}

interface HomeSnapshot {
  todayTrades: TradeHistoryEntry[];
  weekTrades: TradeHistoryEntry[];
  overview: CopyOverview | null;
  riskPolicy: CopyRiskPolicy | null;
}

const emptySnapshot: HomeSnapshot = {
  todayTrades: [],
  weekTrades: [],
  overview: null,
  riskPolicy: null,
};

const previewSnapshot: HomeSnapshot = {
  todayTrades: [
    {
      id: 1,
      ticket: 1000,
      symbol: "GBPUSD",
      order_type: "buy",
      volume: 0.05,
      price_open: 1.34,
      price_close: 1.342,
      sl: 1.336,
      tp: 1.346,
      profit: 0,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-19T06:00:00Z",
      closed_at: "2026-07-19T07:00:00Z",
      source: "copy",
    },
  ],
  weekTrades: [
    {
      id: 2,
      ticket: 998,
      symbol: "EURUSD",
      order_type: "buy",
      volume: 0.05,
      price_open: 1.08,
      price_close: 1.084,
      sl: 1.076,
      tp: 1.088,
      profit: 12.4,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-15T06:00:00Z",
      closed_at: "2026-07-15T08:00:00Z",
      source: "copy",
    },
    {
      id: 3,
      ticket: 999,
      symbol: "XAUUSD",
      order_type: "buy",
      volume: 0.02,
      price_open: 2385,
      price_close: 2397,
      sl: 2374,
      tp: 2405,
      profit: -4.2,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-17T06:00:00Z",
      closed_at: "2026-07-17T08:00:00Z",
      source: "copy",
    },
    {
      id: 4,
      ticket: 1003,
      symbol: "GBPUSD",
      order_type: "sell",
      volume: 0.04,
      price_open: 1.341,
      price_close: 1.338,
      sl: 1.345,
      tp: 1.334,
      profit: 18.75,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-16T06:00:00Z",
      closed_at: "2026-07-16T08:00:00Z",
      source: "copy",
    },
    {
      id: 5,
      ticket: 1004,
      symbol: "EURUSD",
      order_type: "buy",
      volume: 0.05,
      price_open: 1.083,
      price_close: 1.082,
      sl: 1.079,
      tp: 1.091,
      profit: -6.3,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-18T06:00:00Z",
      closed_at: "2026-07-18T08:00:00Z",
      source: "copy",
    },
    {
      id: 6,
      ticket: 1005,
      symbol: "XAUUSD",
      order_type: "buy",
      volume: 0.02,
      price_open: 2398,
      price_close: 2410,
      sl: 2386,
      tp: 2418,
      profit: 44.85,
      swap: 0,
      commission: 0,
      opened_at: "2026-07-19T05:00:00Z",
      closed_at: "2026-07-19T06:30:00Z",
      source: "copy",
    },
  ],
  overview: {
    success: true,
    accounts: [],
    owned_traders: [],
    subscriptions: [
      {
        id: "preview-subscription",
        trader_id: "harbor",
        trader_name: "Harbor Strategy",
        trader_markets: ["EURUSD", "XAUUSD"],
        follower_account_id: "preview-live",
        follower_user_id: "design-preview",
        mode: "paper",
        status: "active",
        risk_preset: "conservative",
        overlap_acknowledged: false,
        country_code: null,
        disclosure_version: null,
        live_activated_at: null,
        created_at: "2026-07-18T08:00:00Z",
        updated_at: "2026-07-19T08:00:00Z",
      },
    ],
    recent_executions: [
      {
        id: "preview-execution-1",
        trader_name: "Harbor Strategy",
        symbol: "XAUUSD",
        action: "modify",
        mode: "paper",
        status: "filled",
        desired_volume: 0.02,
        actual_volume: 0.02,
        blocked_reason: null,
        target_ticket: "1001",
        created_at: "2026-07-19T10:24:00Z",
      },
      {
        id: "preview-execution-2",
        trader_name: "Harbor Strategy",
        symbol: "EURUSD",
        action: "open",
        mode: "paper",
        status: "filled",
        desired_volume: 0.05,
        actual_volume: 0.05,
        blocked_reason: null,
        target_ticket: "1002",
        created_at: "2026-07-19T09:18:00Z",
      },
    ],
    runtimes: [],
    live: { feature_enabled: false, requires_country_eligibility: true },
  },
  riskPolicy: {
    id: "preview-risk",
    account_id: "preview-live",
    preset: "conservative",
    risk_per_trade_pct: 0.25,
    daily_loss_limit_pct: 1,
    total_open_risk_pct: 1,
    max_open_trades: 3,
    require_stop_loss: true,
    allowed_symbols: [],
    updated_at: "2026-07-19T08:00:00Z",
  },
};

function isoDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dashboardRanges(now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const weekStart = new Date(today);
  weekStart.setDate(weekStart.getDate() - 6);

  return {
    todayFrom: isoDate(today),
    todayTo: isoDate(tomorrow),
    weekFrom: isoDate(weekStart),
    weekTo: isoDate(tomorrow),
  };
}

function displayNameFromEmail(email: string) {
  const local = email.split("@")[0] || "there";
  const word = local.split(/[._-]/).find(Boolean) || "there";
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function fullDate() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date());
}

function executionLabel(action: string, traderName: string, symbol: string) {
  const safeTrader = traderName || "A copied trader";
  if (action === "open") return `${safeTrader} opened ${symbol}`;
  if (action === "modify") return `${symbol} protection was updated`;
  if (action === "reduce") return `${safeTrader} reduced ${symbol}`;
  return `${safeTrader} closed ${symbol}`;
}

function dashboardReadiness(
  isConnected: boolean,
  account: AccountInfo | null,
  dailyLossPercent: number | null
) {
  const accountReady = account !== null;
  return {
    accountReady,
    liveDataReady: isConnected && accountReady,
    riskPolicyReady: accountReady && dailyLossPercent !== null,
  };
}

export function ConnectedHome({
  account,
  accountPending = false,
  accountId,
  email,
  isConnected,
  positions,
  preview = false,
  reconnect,
}: ConnectedHomeProps) {
  const [snapshot, setSnapshot] = useState<HomeSnapshot>(preview ? previewSnapshot : emptySnapshot);
  const [loading, setLoading] = useState(!preview);
  const hasAccount = account !== null;

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    async function load(initial = false) {
      if (inFlight) return;
      if (preview) {
        setSnapshot(previewSnapshot);
        setLoading(false);
        return;
      }
      if (!hasAccount || !accountId) {
        setSnapshot(emptySnapshot);
        setLoading(false);
        return;
      }

      inFlight = true;
      if (initial) {
        setSnapshot(emptySnapshot);
        setLoading(true);
      }
      const ranges = dashboardRanges();
      try {
        const [todayResult, weekResult, overviewResult, riskResult] = await Promise.allSettled([
          getTradeHistory(1, 100, undefined, ranges.todayFrom, ranges.todayTo),
          getTradeHistory(1, 500, undefined, ranges.weekFrom, ranges.weekTo),
          getCopyOverview(),
          getCopyRiskPolicy(accountId),
        ]);

        if (cancelled) return;
        setSnapshot((current) => ({
          todayTrades:
            todayResult.status === "fulfilled" ? todayResult.value.trades : current.todayTrades,
          weekTrades:
            weekResult.status === "fulfilled" ? weekResult.value.trades : current.weekTrades,
          overview:
            overviewResult.status === "fulfilled" ? overviewResult.value : current.overview,
          riskPolicy:
            riskResult.status === "fulfilled" ? riskResult.value.risk_policy : current.riskPolicy,
        }));
      } finally {
        inFlight = false;
        if (!cancelled && initial) setLoading(false);
      }
    }

    void load(true);
    const timer = window.setInterval(() => void load(false), 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [accountId, hasAccount, preview]);

  const closedTodayPnL = snapshot.todayTrades.reduce((sum, trade) => sum + trade.profit, 0);
  const floatingPnL = positions.reduce((sum, position) => sum + position.profit, 0);
  const todayPnL = closedTodayPnL + floatingPnL;
  const weekPnL = snapshot.weekTrades.reduce((sum, trade) => sum + trade.profit, 0) + floatingPnL;
  const activeSubscriptions =
    snapshot.overview?.subscriptions.filter((item) => item.status === "active").length ?? 0;
  const dailyLossPercent = snapshot.riskPolicy?.daily_loss_limit_pct ?? null;
  const dailyLossLimit =
    dailyLossPercent === null ? 0 : (account?.balance ?? 0) * (dailyLossPercent / 100);
  const dailyLossUsed = Math.max(0, -todayPnL);
  const dailyLossRemaining = Math.max(0, dailyLossLimit - dailyLossUsed);
  const safetyRemainingPercent =
    dailyLossLimit > 0 ? Math.max(0, Math.min(100, (dailyLossRemaining / dailyLossLimit) * 100)) : 100;
  const chartData = useMemo(
    () => buildEquityCurve(snapshot.weekTrades, account?.equity ?? account?.balance ?? 0),
    [account?.balance, account?.equity, snapshot.weekTrades]
  );
  const recentExecutions = snapshot.overview?.recent_executions.slice(0, 2) ?? [];
  const { accountReady, liveDataReady, riskPolicyReady } = dashboardReadiness(
    isConnected,
    account,
    dailyLossPercent
  );
  const dayTone = todayPnL > 0 ? "positive" : todayPnL < 0 ? "negative" : "steady";

  return (
    <PageContainer className="mx-auto max-w-[1320px] space-y-5">
      <AnimatedSection className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-[-0.035em] text-text-primary">
            Good morning, {displayNameFromEmail(email)}
          </h1>
          <p className="mt-1.5 text-base text-text-secondary">
            {!accountReady
              ? "Your account is set up. We’re waiting for MT5 account data."
              : !liveDataReady
                ? "Showing your latest account snapshot while MT5 reconnects."
              : dayTone === "positive"
                ? `Your account is up ${formatCurrency(todayPnL)} today.`
                : dayTone === "negative"
                  ? `Your account is down ${formatCurrency(Math.abs(todayPnL))} today.`
                  : "Your account is steady today."}
          </p>
        </div>
        <div className="inline-flex w-fit items-center gap-2 rounded-xl border border-border-subtle bg-bg-secondary/50 px-3.5 py-2.5 text-sm text-text-secondary">
          <Clock3 className="h-4 w-4 text-text-muted" />
          {fullDate()}
        </div>
      </AnimatedSection>

      <AnimatedSection>
        <section className="overflow-hidden rounded-[20px] border border-border-default bg-bg-secondary/45 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
          <div className="grid xl:grid-cols-[1.9fr_0.95fr]">
            <div className="min-w-0 border-b border-border-subtle p-5 sm:p-8 xl:border-b-0 xl:border-r">
              <p className="text-base text-text-secondary">Total account value</p>
              {accountReady ? (
                <>
                  <p className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-text-primary tabular-nums sm:text-5xl">
                    {formatCurrency(account?.equity ?? 0)}
                  </p>
                  <div className="mt-7 min-h-[190px]">
                    {loading ? (
                      <Skeleton className="h-[190px] rounded-xl" />
                    ) : (
                      <>
                        <div className="relative overflow-hidden">
                          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[20%] border-t border-dashed border-border-subtle" />
                          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[45%] border-t border-dashed border-border-subtle" />
                          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[70%] border-t border-dashed border-border-subtle" />
                          <EquityChart
                            className="relative z-10"
                            data={chartData}
                            positive={weekPnL >= 0}
                            tone="accent"
                            height={165}
                          />
                        </div>
                        <div className="mt-2 flex justify-between px-1 text-[11px] text-text-muted">
                          <span>7 days ago</span>
                          <span>Today</span>
                        </div>
                      </>
                    )}
                  </div>
                  <p
                    className={cn(
                      "mt-4 text-base font-semibold tabular-nums",
                      weekPnL > 0 ? "text-success" : weekPnL < 0 ? "text-danger" : "text-text-secondary"
                    )}
                  >
                    {weekPnL > 0 ? "Up " : weekPnL < 0 ? "Down " : "No change "}
                    {formatCurrency(Math.abs(weekPnL))}
                    <span className="ml-1 font-normal text-text-muted">this week</span>
                  </p>
                </>
              ) : accountPending ? (
                <div role="status" aria-label="Loading account data">
                  <Skeleton className="mt-2 h-12 w-56 rounded-lg" />
                  <div className="mt-7 min-h-[190px]">
                    <Skeleton className="h-[190px] rounded-xl" delayMs={120} />
                  </div>
                  <Skeleton className="mt-4 h-6 w-44 rounded-lg" delayMs={240} />
                </div>
              ) : (
                <div className="flex min-h-[290px] flex-col items-start justify-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary/70 text-text-muted">
                    <RefreshCw className="h-5 w-5" />
                  </div>
                  <h2 className="mt-5 text-xl font-semibold text-text-primary">Waiting for account data</h2>
                  <p className="mt-2 max-w-md text-sm leading-6 text-text-muted">
                    Your setup is saved. Once MT5 reconnects, your balance and recent activity will appear here automatically.
                  </p>
                  <button
                    type="button"
                    onClick={reconnect}
                    className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl border border-border-default bg-bg-elevated px-4 text-sm font-medium text-text-primary transition-colors hover:border-accent/30 hover:bg-bg-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Try reconnecting
                  </button>
                </div>
              )}
            </div>

            <div className="flex flex-col justify-center p-5 sm:p-8">
              <div className="flex items-center gap-2">
                <h2 className="text-base text-text-secondary">Daily loss limit</h2>
                <span className="group relative">
                  <Info className="h-4 w-4 text-text-muted" />
                  <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-56 -translate-x-1/2 rounded-lg border border-border-default bg-bg-elevated px-3 py-2 text-xs leading-5 text-text-secondary shadow-lg group-hover:block">
                    The maximum loss you allow in one day before new copied trades pause.
                  </span>
                </span>
              </div>
              {riskPolicyReady ? (
                <>
                  <p className="mt-3 text-4xl font-semibold tracking-[-0.035em] text-text-primary tabular-nums">
                    {formatCurrency(dailyLossRemaining)}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    remaining of {formatCurrency(dailyLossLimit)} today
                  </p>
                  <p className="mt-5 text-sm leading-6 text-text-secondary">
                    New copied trades pause automatically before today’s loss reaches this amount.
                  </p>
                  <div className="mt-6">
                    <div className="h-2 overflow-hidden rounded-full bg-bg-elevated">
                      <div
                        className={cn(
                          "h-full rounded-full transition-[width,background-color] duration-500",
                          safetyRemainingPercent > 50
                            ? "bg-success"
                            : safetyRemainingPercent > 20
                              ? "bg-warning"
                              : "bg-danger"
                        )}
                        style={{ width: `${safetyRemainingPercent}%` }}
                      />
                    </div>
                    <div className="mt-2 flex justify-between text-[11px] text-text-muted">
                      <span>Limit available</span>
                      <span>{dailyLossPercent}% of balance</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="mt-4 rounded-xl border border-border-subtle bg-bg-tertiary/35 p-4 text-sm leading-6 text-text-muted">
                  {accountReady
                    ? "Your safety limit could not be loaded. Review it before starting new copied trades."
                    : "Your selected limit will appear when MT5 reconnects."}
                </div>
              )}
              <Link
                href="/copy-trading"
                className="mt-7 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-accent-light/25 bg-accent px-5 text-sm font-semibold text-bg-primary transition-[background-color,transform] hover:bg-accent-light active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-light focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
              >
                Review safety limits
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>
      </AnimatedSection>

      <AnimatedSection className="grid gap-5 xl:grid-cols-2">
        <section className="rounded-[20px] border border-border-default bg-bg-secondary/40 p-5 sm:p-7">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold text-text-primary">Today at a glance</h2>
            <Link href="/positions" className="text-xs font-medium text-accent hover:text-accent-light">
              View positions
            </Link>
          </div>
          <div className="mt-5 divide-y divide-border-subtle">
            <GlanceRow
              icon={Activity}
              label="Open trades"
              description="Trades currently open"
              value={accountReady ? String(positions.length) : "—"}
            />
            <GlanceRow
              icon={CircleDollarSign}
              label="Result so far"
              description="Profit or loss today"
              value={accountReady ? `${todayPnL >= 0 ? "+" : ""}${formatCurrency(todayPnL)}` : "—"}
              tone={todayPnL > 0 ? "success" : todayPnL < 0 ? "danger" : "neutral"}
            />
            <GlanceRow
              icon={UsersRound}
              label="Copied traders"
              description="Traders currently active"
              value={accountReady ? `${activeSubscriptions} active` : "—"}
              tone="accent"
            />
          </div>
        </section>

        <section className="rounded-[20px] border border-border-default bg-bg-secondary/40 p-5 sm:p-7">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold text-text-primary">What changed</h2>
            <BarChart3 className="h-5 w-5 text-text-muted" />
          </div>
          <div className="mt-6 min-h-[220px]">
            {!accountReady ? (
              <EmptyActivity
                title="Activity will appear after MT5 reconnects"
                description="Your setup is safe; we simply don’t have live account updates yet."
              />
            ) : recentExecutions.length > 0 ? (
              <div className="space-y-5">
                {recentExecutions.map((item) => (
                  <div key={item.id} className="flex gap-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-tertiary/60 text-success">
                      {item.action === "modify" ? (
                        <ShieldCheck className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text-primary">
                        {executionLabel(item.action, item.trader_name, item.symbol)}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-text-muted">
                        {item.blocked_reason
                          ? `This update was paused: ${item.blocked_reason}.`
                          : `${item.mode === "paper" ? "Paper" : "Live"} copy update recorded successfully.`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : snapshot.todayTrades.length > 0 ? (
              <div className="space-y-5">
                {snapshot.todayTrades.slice(0, 2).map((trade) => (
                  <div key={trade.id} className="flex gap-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-tertiary/60 text-accent">
                      <CheckCircle2 className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-sm font-medium text-text-primary">{trade.symbol} trade closed</p>
                      <p className="mt-1 text-xs text-text-muted">
                        Result {formatCurrency(trade.profit)} · {trade.source === "copy" ? "Copied trade" : "Your trade"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyActivity
                title="No trading changes today"
                description="New trades, safety updates, and closures will be explained here in plain language."
              />
            )}
          </div>
          <Link
            href="/history"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-light"
          >
            See activity
            <ChevronRight className="h-4 w-4" />
          </Link>
        </section>
      </AnimatedSection>

      <span className="sr-only" aria-live="polite">
        {accountReady
          ? `Account value ${formatCurrency(account?.equity ?? 0)}. ${positions.length} open trades.`
          : "Waiting for MT5 account data."}
      </span>
    </PageContainer>
  );
}

function GlanceRow({
  icon: Icon,
  label,
  description,
  value,
  tone = "neutral",
}: {
  icon: typeof Activity;
  label: string;
  description: string;
  value: string;
  tone?: "neutral" | "success" | "danger" | "accent";
}) {
  return (
    <div className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-tertiary/55 text-accent">
        <Icon className="h-5 w-5" strokeWidth={1.7} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-text-primary">{label}</span>
        <span className="mt-0.5 block text-xs text-text-muted">{description}</span>
      </span>
      <span
        className={cn(
          "shrink-0 text-lg font-semibold tabular-nums",
          tone === "success" && "text-success",
          tone === "danger" && "text-danger",
          tone === "accent" && "text-accent",
          tone === "neutral" && "text-text-primary"
        )}
      >
        {value}
      </span>
    </div>
  );
}

function EmptyActivity({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex min-h-[190px] flex-col items-center justify-center rounded-xl border border-dashed border-border-default bg-bg-primary/20 px-6 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-border-subtle bg-bg-tertiary/55 text-text-muted">
        <Activity className="h-5 w-5" />
      </span>
      <p className="mt-4 text-sm font-medium text-text-primary">{title}</p>
      <p className="mt-1 max-w-sm text-xs leading-5 text-text-muted">{description}</p>
    </div>
  );
}

export const homeDashboardTestHelpers = {
  dashboardReadiness,
  dashboardRanges,
  displayNameFromEmail,
  executionLabel,
};
