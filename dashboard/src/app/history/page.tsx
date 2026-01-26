"use client";

import { useState, useEffect, useMemo, Fragment } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { GlassCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PnlBadge } from "@/components/dashboard/pnl-badge";
import {
  TimeRangeFilter,
  type TimePreset,
  type DateRange,
} from "@/components/history/time-range-filter";
import { getTradeHistory } from "@/lib/api";
import { formatDateTime, formatNumber, formatCurrency, cn } from "@/lib/utils";
import type { TradeHistoryEntry } from "@/types";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  History,
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
  Calendar,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

type GroupingMode = "none" | "day" | "week";

interface TradeGroup {
  key: string;
  label: string;
  sublabel?: string;
  trades: TradeHistoryEntry[];
  totalProfit: number;
  winCount: number;
}

function getGroupingMode(preset: TimePreset): GroupingMode {
  if (preset === "this_week") return "day";
  if (preset === "this_month") return "week";
  return "none";
}

function getDateFromTrade(trade: TradeHistoryEntry): Date {
  const timestamp = trade.closed_at;
  if (typeof timestamp === "number") {
    return new Date(timestamp * 1000);
  }
  return new Date(timestamp);
}

function formatDayLabel(date: Date): string {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const isToday = date.toDateString() === today.toDateString();
  const isYesterday = date.toDateString() === yesterday.toDateString();

  if (isToday) return "Today";
  if (isYesterday) return "Yesterday";

  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

function formatWeekLabel(weekStart: Date): string {
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 6);

  const now = new Date();
  const currentWeekStart = getWeekStart(now);

  if (weekStart.toDateString() === currentWeekStart.toDateString()) {
    return "This Week";
  }

  const lastWeekStart = new Date(currentWeekStart);
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);
  if (weekStart.toDateString() === lastWeekStart.toDateString()) {
    return "Last Week";
  }

  return `${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} - ${weekEnd.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

function getWeekStart(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? 6 : day - 1; // Monday as start
  d.setDate(d.getDate() - diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getDayKey(date: Date): string {
  return date.toISOString().split("T")[0];
}

function getWeekKey(date: Date): string {
  const weekStart = getWeekStart(date);
  return weekStart.toISOString().split("T")[0];
}

function groupTrades(
  trades: TradeHistoryEntry[],
  mode: GroupingMode
): TradeGroup[] {
  if (mode === "none") {
    return [];
  }

  const groups = new Map<string, TradeGroup>();

  for (const trade of trades) {
    const date = getDateFromTrade(trade);
    let key: string;
    let label: string;
    let sublabel: string | undefined;

    if (mode === "day") {
      key = getDayKey(date);
      label = formatDayLabel(date);
      sublabel = date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } else {
      key = getWeekKey(date);
      const weekStart = getWeekStart(date);
      label = formatWeekLabel(weekStart);
      sublabel = `Week of ${weekStart.toLocaleDateString("en-US", { month: "long", day: "numeric" })}`;
    }

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label,
        sublabel,
        trades: [],
        totalProfit: 0,
        winCount: 0,
      });
    }

    const group = groups.get(key)!;
    group.trades.push(trade);
    group.totalProfit += trade.profit;
    if (trade.profit > 0) group.winCount++;
  }

  // Sort groups by date descending
  return Array.from(groups.values()).sort((a, b) => b.key.localeCompare(a.key));
}

function TradeRow({ trade }: { trade: TradeHistoryEntry }) {
  return (
    <tr className="border-b border-border-subtle last:border-0 group">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-bg-tertiary flex items-center justify-center">
            <span className="text-xs font-semibold text-accent">
              {trade.symbol.slice(0, 2)}
            </span>
          </div>
          <span className="font-medium text-text-primary text-sm">
            {trade.symbol}
          </span>
        </div>
      </td>
      <td className="px-6 py-4">
        <Badge
          variant={trade.order_type === "buy" ? "success" : "danger"}
          className="gap-1"
        >
          {trade.order_type === "buy" ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          {trade.order_type.toUpperCase()}
        </Badge>
      </td>
      <td className="px-6 py-4 text-right">
        <span className="text-sm text-text-primary tabular-nums font-medium">
          {trade.volume.toFixed(2)}
        </span>
      </td>
      <td className="px-6 py-4 text-right">
        <span className="text-sm text-text-secondary tabular-nums font-mono">
          {formatNumber(trade.price_open, 5)}
        </span>
      </td>
      <td className="px-6 py-4 text-right">
        <span className="text-sm text-text-primary tabular-nums font-mono">
          {formatNumber(trade.price_close, 5)}
        </span>
      </td>
      <td className="px-6 py-4 text-right">
        <PnlBadge value={trade.profit} />
      </td>
      <td className="px-6 py-4">
        <span className="text-sm text-text-muted">
          {formatDateTime(trade.closed_at)}
        </span>
      </td>
      <td className="px-6 py-4">
        <Badge variant="default" size="sm">
          {trade.source}
        </Badge>
      </td>
    </tr>
  );
}

function GroupHeader({
  group,
  isExpanded,
  onToggle,
}: {
  group: TradeGroup;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const winRate =
    group.trades.length > 0
      ? ((group.winCount / group.trades.length) * 100).toFixed(0)
      : 0;

  return (
    <tr
      className="bg-bg-tertiary/50 border-b border-border-subtle cursor-pointer hover:bg-bg-tertiary/70 transition-colors"
      onClick={onToggle}
    >
      <td colSpan={8} className="px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
                group.totalProfit >= 0
                  ? "bg-success/10 border border-success/20"
                  : "bg-danger/10 border border-danger/20"
              )}
            >
              <Calendar
                className={cn(
                  "w-4 h-4",
                  group.totalProfit >= 0 ? "text-success" : "text-danger"
                )}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-text-primary">
                  {group.label}
                </span>
                <ChevronDown
                  className={cn(
                    "w-4 h-4 text-text-muted transition-transform",
                    isExpanded && "rotate-180"
                  )}
                />
              </div>
              {group.sublabel && group.label !== group.sublabel && (
                <span className="text-xs text-text-muted">{group.sublabel}</span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-xs text-text-muted">Trades</p>
              <p className="text-sm font-medium text-text-primary tabular-nums">
                {group.trades.length}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-text-muted">Win Rate</p>
              <p className="text-sm font-medium text-text-primary tabular-nums">
                {winRate}%
              </p>
            </div>
            <div className="text-right min-w-[100px]">
              <p className="text-xs text-text-muted">P&L</p>
              <p
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  group.totalProfit >= 0 ? "text-success" : "text-danger"
                )}
              >
                {group.totalProfit >= 0 ? "+" : ""}
                {formatCurrency(group.totalProfit)}
              </p>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}

export default function HistoryPage() {
  const [trades, setTrades] = useState<TradeHistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [timePreset, setTimePreset] = useState<TimePreset>("all");
  const [dateRange, setDateRange] = useState<DateRange>({
    from: null,
    to: null,
  });
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const pageSize = 20;

  const totalPages = Math.ceil(total / pageSize);
  const groupingMode = getGroupingMode(timePreset);

  const groups = useMemo(() => {
    return groupTrades(trades, groupingMode);
  }, [trades, groupingMode]);

  // Expand all groups by default when grouping changes
  useEffect(() => {
    if (groupingMode !== "none") {
      setExpandedGroups(new Set(groups.map((g) => g.key)));
    }
  }, [groupingMode, groups]);

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const result = await getTradeHistory(
          page,
          pageSize,
          undefined,
          dateRange.from || undefined,
          dateRange.to || undefined
        );
        setTrades(result.trades);
        setTotal(result.total);
      } catch (error) {
        console.error("Failed to fetch trade history:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [page, dateRange]);

  const handleTimeRangeChange = (preset: TimePreset, range: DateRange) => {
    setTimePreset(preset);
    setDateRange(range);
    setPage(1);
  };

  // Calculate stats
  const totalProfit = trades.reduce((sum, t) => sum + t.profit, 0);
  const winningTrades = trades.filter((t) => t.profit > 0).length;

  return (
    <PageContainer>
      {/* Page Header */}
      <AnimatedSection className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
            Trade History
          </h1>
          <p className="text-sm text-text-muted mt-1">
            View your closed trades and performance
          </p>
        </div>
        <TimeRangeFilter
          value={timePreset}
          dateRange={dateRange}
          onChange={handleTimeRangeChange}
        />
      </AnimatedSection>

      {/* Stats */}
      <AnimatedSection className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard className="group hover:border-accent/20">
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-accent" />
            </div>
          </div>
          <p className="text-xs text-text-muted mb-1">Total Trades</p>
          <p className="text-2xl font-semibold text-text-primary tabular-nums">
            {total}
          </p>
        </GlassCard>

        <GlassCard className="group hover:border-success/20">
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 border border-success/20 flex items-center justify-center">
              <Target className="w-5 h-5 text-success" />
            </div>
          </div>
          <p className="text-xs text-text-muted mb-1">Win Rate</p>
          <p className="text-2xl font-semibold text-success tabular-nums">
            {trades.length > 0
              ? ((winningTrades / trades.length) * 100).toFixed(1)
              : 0}
            %
          </p>
        </GlassCard>

        <GlassCard
          className={`group ${
            totalProfit >= 0
              ? "hover:border-success/20"
              : "hover:border-danger/20"
          }`}
        >
          <div className="flex items-start justify-between mb-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                totalProfit >= 0
                  ? "bg-success/10 border border-success/20"
                  : "bg-danger/10 border border-danger/20"
              }`}
            >
              {totalProfit >= 0 ? (
                <TrendingUp className="w-5 h-5 text-success" />
              ) : (
                <TrendingDown className="w-5 h-5 text-danger" />
              )}
            </div>
          </div>
          <p className="text-xs text-text-muted mb-1">Page P&L</p>
          <p
            className={`text-2xl font-semibold tabular-nums ${
              totalProfit >= 0 ? "text-success" : "text-danger"
            }`}
          >
            {totalProfit >= 0 ? "+" : ""}
            {formatCurrency(totalProfit)}
          </p>
        </GlassCard>
      </AnimatedSection>

      {/* History Table */}
      <AnimatedSection>
        <Card>
        <CardHeader className="flex flex-row items-center justify-between bg-bg-tertiary/30">
          <div className="flex items-center gap-3">
            <CardTitle>Closed Trades</CardTitle>
            {groupingMode !== "none" && (
              <Badge variant="default" size="sm">
                Grouped by {groupingMode === "day" ? "Day" : "Week"}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || isLoading}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-text-secondary tabular-nums px-2">
              {page} / {totalPages || 1}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || isLoading}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center animate-pulse">
                <History className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-text-muted">Loading trade history...</p>
            </div>
          ) : trades.length === 0 ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center">
                <History className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-text-secondary mb-1">No trade history</p>
              <p className="text-sm text-text-muted">
                Your closed trades will appear here
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="px-6 py-3 text-left">Symbol</th>
                    <th className="px-6 py-3 text-left">Type</th>
                    <th className="px-6 py-3 text-right">Volume</th>
                    <th className="px-6 py-3 text-right">Open</th>
                    <th className="px-6 py-3 text-right">Close</th>
                    <th className="px-6 py-3 text-right">P&L</th>
                    <th className="px-6 py-3 text-left">Closed At</th>
                    <th className="px-6 py-3 text-left">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {groupingMode === "none" ? (
                    // Flat list - no grouping
                    trades.map((trade) => (
                      <TradeRow key={trade.id} trade={trade} />
                    ))
                  ) : (
                    // Grouped view
                    groups.map((group) => (
                      <Fragment key={group.key}>
                        <GroupHeader
                          group={group}
                          isExpanded={expandedGroups.has(group.key)}
                          onToggle={() => toggleGroup(group.key)}
                        />
                        {expandedGroups.has(group.key) &&
                          group.trades.map((trade) => (
                            <TradeRow key={trade.id} trade={trade} />
                          ))}
                      </Fragment>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      </AnimatedSection>
    </PageContainer>
  );
}
