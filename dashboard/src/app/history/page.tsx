"use client";

import { useState, useEffect, useMemo, Fragment } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { Skeleton } from "@/components/amicro/skeleton";
import { PageHeader, SectionPanel, PanelHeader, PanelBody, EmptyState } from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { MetricCard } from "@/components/dashboard/metric-card";
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
import { SymbolCell } from "@/components/dashboard/symbol-icon";
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
        <SymbolCell symbol={trade.symbol} size="sm" />
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

const loadingCellWidths = [
  "w-24",
  "w-14",
  "w-10",
  "w-20",
  "w-20",
  "w-16",
  "w-24",
  "w-12",
];

function HistoryTableLoading() {
  return (
    <div
      className="relative min-h-[360px] overflow-hidden"
      role="status"
      aria-live="polite"
      aria-label="Loading trade history"
    >
      <div className="flex items-center gap-3 border-b border-border-subtle bg-bg-tertiary/20 px-6 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-accent/20 bg-accent/10 text-accent shadow-[0_0_24px_rgba(96,165,250,0.12)]">
          <IOSSpinner size={16} />
        </span>
        <div>
          <p className="text-sm font-medium text-text-primary">
            Loading trade records
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            Syncing your latest closed trades from MT5
          </p>
        </div>
        <span className="ml-auto hidden items-center gap-2 text-[10px] font-medium uppercase tracking-[0.16em] text-text-muted sm:flex">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          Live sync
        </span>
      </div>

      <div className="overflow-x-auto" aria-hidden="true">
        <table className="w-full data-table">
          <thead>
            <tr className="border-b border-border-subtle bg-bg-tertiary/30">
              <th className="px-6 py-3 text-left">Symbol</th>
              <th className="px-6 py-3 text-left">Type</th>
              <th className="px-6 py-3 text-right">Volume</th>
              <th className="px-6 py-3 text-right">Open</th>
              <th className="px-6 py-3 text-right">Close</th>
              <th className="px-6 py-3 text-right">P&amp;L</th>
              <th className="px-6 py-3 text-left">Closed At</th>
              <th className="px-6 py-3 text-left">Source</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }, (_, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-border-subtle last:border-0"
              >
                {loadingCellWidths.map((width, cellIndex) => (
                  <td
                    key={cellIndex}
                    className={cn(
                      "px-6 py-4",
                      cellIndex >= 2 && cellIndex <= 5 && "text-right"
                    )}
                  >
                    <Skeleton
                      className={cn(
                        "h-3 rounded-full",
                        width,
                        cellIndex >= 2 && cellIndex <= 5 && "ml-auto"
                      )}
                      delayMs={rowIndex * 90 + cellIndex * 35}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const { session, designPreview } = useDashboard();
  const [trades, setTrades] = useState<TradeHistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(!designPreview);
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
    if (designPreview) return;
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
  }, [dateRange, designPreview, page, session.activeAccountId]);

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
      <AnimatedSection>
        <PageHeader
          meta="Performance"
          title="Trade history"
          description="Closed trades and realized P&L"
          actions={
            <TimeRangeFilter
              value={timePreset}
              dateRange={dateRange}
              onChange={handleTimeRangeChange}
            />
          }
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Total trades"
          value={String(total)}
          icon={<BarChart3 className="w-5 h-5" />}
          accent="accent"
        />
        <MetricCard
          label="Win rate"
          value={`${
            trades.length > 0
              ? ((winningTrades / trades.length) * 100).toFixed(1)
              : 0
          }%`}
          icon={<Target className="w-5 h-5" />}
          accent="success"
        />
        <MetricCard
          label="Page P&L"
          value={`${totalProfit >= 0 ? "+" : ""}${formatCurrency(totalProfit)}`}
          icon={
            totalProfit >= 0 ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )
          }
          accent={totalProfit >= 0 ? "success" : "danger"}
        />
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
        <PanelHeader
          eyebrow="History"
          title={
            <span className="inline-flex items-center gap-2">
              Closed trades
              {groupingMode !== "none" && (
                <Badge variant="default" size="sm">
                  Grouped by {groupingMode === "day" ? "day" : "week"}
                </Badge>
              )}
            </span>
          }
          action={
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
          }
        />
        <PanelBody flush>
          {isLoading ? (
            <HistoryTableLoading />
          ) : trades.length === 0 ? (
            <EmptyState
              icon={<History className="w-5 h-5" />}
              title="No trade history"
              description="Your closed trades will appear here"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr className="border-b border-border-subtle bg-bg-tertiary/30">
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
        </PanelBody>
      </SectionPanel>
      </AnimatedSection>
    </PageContainer>
  );
}
