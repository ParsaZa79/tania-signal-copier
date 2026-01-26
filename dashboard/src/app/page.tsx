"use client";

import { useState, useEffect } from "react";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { AccountCard } from "@/components/dashboard/account-card";
import { PositionsTable } from "@/components/dashboard/positions-table";
import { GlassCard } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import { getTradeHistory } from "@/lib/api";
import type { TradeHistoryEntry } from "@/types";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  Target,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

function getTodayDateRange() {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  return {
    from: today.toISOString().split("T")[0],
    to: tomorrow.toISOString().split("T")[0],
  };
}

export default function DashboardPage() {
  const { positions, account } = useDashboard();
  const [todayTrades, setTodayTrades] = useState<TradeHistoryEntry[]>([]);
  const [isLoadingTrades, setIsLoadingTrades] = useState(true);

  // Fetch today's closed trades
  useEffect(() => {
    const fetchTodayTrades = async () => {
      setIsLoadingTrades(true);
      try {
        const { from, to } = getTodayDateRange();
        const result = await getTradeHistory(1, 100, undefined, from, to);
        setTodayTrades(result.trades);
      } catch (error) {
        console.error("Failed to fetch today's trades:", error);
      } finally {
        setIsLoadingTrades(false);
      }
    };

    fetchTodayTrades();
    // Refresh every 30 seconds
    const interval = setInterval(fetchTodayTrades, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate open positions stats
  const floatingPnL = positions.reduce((sum, pos) => sum + pos.profit, 0);
  const winningPositions = positions.filter((pos) => pos.profit > 0).length;
  const losingPositions = positions.filter((pos) => pos.profit < 0).length;
  const positionsWinRate =
    positions.length > 0
      ? ((winningPositions / positions.length) * 100).toFixed(1)
      : "0";

  // Calculate today's closed trades stats
  const todayPnL = todayTrades.reduce((sum, t) => sum + t.profit, 0);
  const todayWins = todayTrades.filter((t) => t.profit > 0).length;
  const todayLosses = todayTrades.filter((t) => t.profit < 0).length;
  const todayWinRate =
    todayTrades.length > 0
      ? ((todayWins / todayTrades.length) * 100).toFixed(0)
      : "0";

  return (
    <PageContainer>
      {/* Page Header */}
      <AnimatedSection className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
            Overview
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Real-time trading performance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Last updated</span>
          <span className="text-xs text-text-secondary tabular-nums">
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      </AnimatedSection>

      {/* Stats Grid */}
      <AnimatedSection className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Account Balance */}
        <AccountCard account={account} />

        {/* Open Positions */}
        <GlassCard className="group hover:border-accent/20 transition-all duration-300">
          <div className="flex items-start justify-between mb-4">
            <div className="w-11 h-11 rounded-xl bg-info/10 border border-info/20 flex items-center justify-center">
              <Activity className="w-5 h-5 text-info" />
            </div>
            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-bg-tertiary">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[10px] text-text-muted">Live</span>
            </div>
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Open Positions</p>
            <p className="text-3xl font-semibold text-text-primary tabular-nums">
              {positions.length}
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-border-subtle">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <ArrowUpRight className="w-3 h-3 text-success" />
                  <span className="text-xs text-success tabular-nums">
                    {winningPositions}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <ArrowDownRight className="w-3 h-3 text-danger" />
                  <span className="text-xs text-danger tabular-nums">
                    {losingPositions}
                  </span>
                </div>
              </div>
              <span className="text-[10px] text-text-muted">
                Win Rate: {positionsWinRate}%
              </span>
            </div>
          </div>
        </GlassCard>

        {/* Floating P&L */}
        <GlassCard
          className={`group transition-all duration-300 ${
            floatingPnL >= 0
              ? "hover:border-success/20"
              : "hover:border-danger/20"
          }`}
        >
          <div className="flex items-start justify-between mb-4">
            <div
              className={`w-11 h-11 rounded-xl flex items-center justify-center ${
                floatingPnL >= 0
                  ? "bg-success/10 border border-success/20"
                  : "bg-danger/10 border border-danger/20"
              }`}
            >
              {floatingPnL >= 0 ? (
                <TrendingUp className="w-5 h-5 text-success" />
              ) : (
                <TrendingDown className="w-5 h-5 text-danger" />
              )}
            </div>
            <MiniSparkline positive={floatingPnL >= 0} />
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Floating P&L</p>
            <p
              className={`text-3xl font-semibold tabular-nums ${
                floatingPnL >= 0 ? "text-success" : "text-danger"
              }`}
            >
              {floatingPnL >= 0 ? "+" : ""}
              {formatCurrency(floatingPnL)}
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-border-subtle">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">
                From {positions.length} position{positions.length !== 1 && "s"}
              </span>
              <div
                className={`flex items-center gap-1 ${
                  floatingPnL >= 0 ? "text-success" : "text-danger"
                }`}
              >
                {floatingPnL >= 0 ? (
                  <ArrowUpRight className="w-3 h-3" />
                ) : (
                  <ArrowDownRight className="w-3 h-3" />
                )}
                <span className="text-xs font-medium tabular-nums">
                  {account?.balance
                    ? ((floatingPnL / account.balance) * 100).toFixed(2)
                    : "0.00"}
                  %
                </span>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Today's Closed P&L */}
        <GlassCard
          className={`group transition-all duration-300 ${
            todayPnL >= 0
              ? "hover:border-success/20"
              : "hover:border-danger/20"
          }`}
        >
          <div className="flex items-start justify-between mb-4">
            <div
              className={`w-11 h-11 rounded-xl flex items-center justify-center ${
                todayPnL >= 0
                  ? "bg-accent/10 border border-accent/20"
                  : "bg-danger/10 border border-danger/20"
              }`}
            >
              <BarChart3
                className={`w-5 h-5 ${todayPnL >= 0 ? "text-accent" : "text-danger"}`}
              />
            </div>
            <div className="text-right">
              <span className="text-[10px] text-text-muted">Today</span>
            </div>
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Closed P&L</p>
            {isLoadingTrades ? (
              <div className="h-9 flex items-center">
                <div className="w-24 h-6 bg-bg-tertiary rounded animate-pulse" />
              </div>
            ) : (
              <p
                className={`text-3xl font-semibold tabular-nums ${
                  todayPnL >= 0 ? "text-success" : "text-danger"
                }`}
              >
                {todayPnL >= 0 ? "+" : ""}
                {formatCurrency(todayPnL)}
              </p>
            )}
          </div>
          <div className="mt-4 pt-4 border-t border-border-subtle">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">
                  {todayTrades.length} trade{todayTrades.length !== 1 && "s"}
                </span>
                {todayTrades.length > 0 && (
                  <>
                    <div className="flex items-center gap-1">
                      <ArrowUpRight className="w-3 h-3 text-success" />
                      <span className="text-xs text-success tabular-nums">
                        {todayWins}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <ArrowDownRight className="w-3 h-3 text-danger" />
                      <span className="text-xs text-danger tabular-nums">
                        {todayLosses}
                      </span>
                    </div>
                  </>
                )}
              </div>
              {todayTrades.length > 0 && (
                <div className="flex items-center gap-1">
                  <Target className="w-3 h-3 text-text-muted" />
                  <span className="text-xs text-text-secondary tabular-nums">
                    {todayWinRate}%
                  </span>
                </div>
              )}
            </div>
          </div>
        </GlassCard>
      </AnimatedSection>

      {/* Secondary Stats Row */}
      <AnimatedSection className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatPill
          label="Equity"
          value={formatCurrency(account?.equity || 0)}
          icon={<Wallet className="w-4 h-4" />}
          color="accent"
        />
        <StatPill
          label="Margin Used"
          value={formatCurrency(account?.margin || 0)}
          icon={<Activity className="w-4 h-4" />}
          color="info"
        />
        <StatPill
          label="Free Margin"
          value={formatCurrency(account?.free_margin || 0)}
          icon={<TrendingUp className="w-4 h-4" />}
          color="success"
        />
        <StatPill
          label="Margin Level"
          value={
            account?.margin && account.margin > 0
              ? `${((account.equity / account.margin) * 100).toFixed(0)}%`
              : "N/A"
          }
          icon={<BarChart3 className="w-4 h-4" />}
          color="warning"
          highlight={
            account?.margin && account.margin > 0
              ? (account.equity / account.margin) * 100 > 200
              : false
          }
        />
      </AnimatedSection>

      {/* Positions Table */}
      <AnimatedSection>
        <PositionsTable positions={positions} />
      </AnimatedSection>
    </PageContainer>
  );
}

// Mini sparkline component
function MiniSparkline({ positive }: { positive: boolean }) {
  const points = positive
    ? "0,20 10,18 20,15 30,17 40,12 50,14 60,8 70,10 80,5 90,7 100,3"
    : "0,5 10,8 20,6 30,12 40,10 50,15 60,13 70,18 80,16 90,20 100,17";

  return (
    <svg width="60" height="24" viewBox="0 0 100 24" className="opacity-60">
      <polyline
        points={points}
        className="sparkline"
        stroke={positive ? "var(--success)" : "var(--danger)"}
      />
    </svg>
  );
}

// Stat pill component
function StatPill({
  label,
  value,
  icon,
  color,
  highlight = false,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: "accent" | "info" | "success" | "warning";
  highlight?: boolean;
}) {
  const colorStyles = {
    accent: {
      bg: "bg-accent/10",
      border: "border-accent/20",
      text: "text-accent",
      gradient: "from-accent/10 to-transparent",
    },
    info: {
      bg: "bg-info/10",
      border: "border-info/20",
      text: "text-info",
      gradient: "from-info/10 to-transparent",
    },
    success: {
      bg: "bg-success/10",
      border: "border-success/20",
      text: "text-success",
      gradient: "from-success/10 to-transparent",
    },
    warning: {
      bg: "bg-warning/10",
      border: "border-warning/20",
      text: "text-warning",
      gradient: "from-warning/10 to-transparent",
    },
  };

  const styles = colorStyles[color];

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200 bg-gradient-to-r ${styles.gradient} ${styles.border} hover:border-opacity-50`}
    >
      <div
        className={`w-9 h-9 rounded-lg flex items-center justify-center ${styles.bg} ${styles.text}`}
      >
        {icon}
      </div>
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wide">
          {label}
        </p>
        <p className={`text-sm font-semibold tabular-nums ${highlight ? styles.text : "text-text-primary"}`}>
          {value}
        </p>
      </div>
    </div>
  );
}
