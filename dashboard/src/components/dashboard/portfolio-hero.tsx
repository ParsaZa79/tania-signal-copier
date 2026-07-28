"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Skeleton } from "@/components/amicro/skeleton";
import { getTradeHistory } from "@/lib/api";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import type { AccountInfo } from "@/types";
import {
  TimeRangeSelector,
  getDateRangeForTimeRange,
  type TimeRange,
} from "./time-range-selector";
import { EquityChart, buildEquityCurve } from "./equity-chart";

interface PortfolioHeroProps {
  account: AccountInfo | null;
  floatingPnL: number;
  accountId: string | null;
}

export function PortfolioHero({ account, floatingPnL, accountId }: PortfolioHeroProps) {
  const [range, setRange] = useState<TimeRange>("1M");
  const [periodPnL, setPeriodPnL] = useState(0);
  const [tradeCount, setTradeCount] = useState(0);
  const [chartData, setChartData] = useState<
    ReturnType<typeof buildEquityCurve>
  >([]);
  const [isLoading, setIsLoading] = useState(true);

  const equity = account?.equity ?? 0;
  const balance = account?.balance ?? 0;
  const hasAccountConnection = account !== null;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!hasAccountConnection) {
        setPeriodPnL(0);
        setTradeCount(0);
        setChartData(buildEquityCurve([], 0));
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const { from, to } = getDateRangeForTimeRange(range);
        const result = await getTradeHistory(1, 500, undefined, from, to);
        if (cancelled) return;

        const pnl = result.trades.reduce((sum, t) => sum + t.profit, 0);
        setPeriodPnL(pnl);
        setTradeCount(result.trades.length);
        setChartData(buildEquityCurve(result.trades, equity || balance));
      } catch {
        if (!cancelled) {
          setPeriodPnL(0);
          setTradeCount(0);
          setChartData(buildEquityCurve([], equity || balance));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [hasAccountConnection, range, equity, balance, accountId]);

  const changePercent = useMemo(() => {
    const base = balance > 0 ? balance : equity;
    if (base <= 0) return 0;
    return ((periodPnL + floatingPnL) / base) * 100;
  }, [balance, equity, periodPnL, floatingPnL]);

  const isPositive = periodPnL + floatingPnL >= 0;
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <section className="rounded-2xl border border-border-subtle bg-bg-secondary/60 overflow-hidden">
      <div className="p-6 pb-4 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <p className="text-sm text-text-muted">{today}</p>
          <h2 className="text-lg font-medium text-text-primary mt-1">
            {isPositive ? "Portfolio is up" : "Portfolio is down"}{" "}
            <span className={isPositive ? "text-success" : "text-danger"}>
              {formatPercent(changePercent)}
            </span>
          </h2>
        </div>
        <TimeRangeSelector value={range} onChange={setRange} />
      </div>

      <div className="px-6 pb-2">
        <p className="text-xs font-medium uppercase tracking-wider text-text-muted mb-2">
          Account Equity
        </p>
        {account ? (
          <div className="flex flex-wrap items-end gap-4">
            <p className="text-4xl lg:text-5xl font-semibold text-text-primary tabular-nums tracking-tight">
              {formatCurrency(equity)}
            </p>
            <div
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium tabular-nums border mb-1",
                isPositive
                  ? "bg-success/10 text-success border-success/20"
                  : "bg-danger/10 text-danger border-danger/20"
              )}
            >
              {isPositive ? (
                <ArrowUpRight className="w-4 h-4" />
              ) : (
                <ArrowDownRight className="w-4 h-4" />
              )}
              {formatCurrency(periodPnL + floatingPnL)}
              <span className="text-text-muted font-normal">
                ({tradeCount} closed · {formatCurrency(floatingPnL)} open)
              </span>
            </div>
          </div>
        ) : (
          <Skeleton className="h-12 w-48 rounded-lg" />
        )}
      </div>

      <div className="px-2 pb-4 pt-2">
        {isLoading ? (
          <Skeleton className="mx-4 h-[120px] rounded-xl" />
        ) : (
          <EquityChart data={chartData} positive={isPositive} height={120} />
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-border-subtle divide-x divide-border-subtle">
        <HeroStat label="Balance" value={formatCurrency(balance)} />
        <HeroStat
          label="Floating P&L"
          value={formatCurrency(floatingPnL)}
          tone={floatingPnL >= 0 ? "success" : "danger"}
        />
        <HeroStat label="Margin Used" value={formatCurrency(account?.margin ?? 0)} />
        <HeroStat
          label="Free Margin"
          value={formatCurrency(account?.free_margin ?? 0)}
          tone="accent"
        />
      </div>
    </section>
  );
}

function HeroStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "success" | "danger" | "accent";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-danger"
        : tone === "accent"
          ? "text-accent"
          : "text-text-primary";

  return (
    <div className="px-6 py-4">
      <p className="text-[10px] uppercase tracking-wider text-text-muted mb-1">
        {label}
      </p>
      <p className={cn("text-sm font-semibold tabular-nums", toneClass)}>
        {value}
      </p>
    </div>
  );
}
