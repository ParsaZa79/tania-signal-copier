"use client";

import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Check,
  CircleAlert,
  Clock3,
  Globe2,
  Info,
  LockKeyhole,
  Pause,
  Play,
  Radio,
  Search,
  ShieldCheck,
  TrendingDown,
  UsersRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { PulseDots } from "@/components/amicro/pulse-dots";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  activateLiveCopySubscription,
  createCopySubscription,
  getCopyDirectory,
  getCopyOverview,
  saveCopyRiskPolicy,
  saveCopyTrader,
  updateCopySubscription,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  CopyAccount,
  CopyOverview,
  CopySubscription,
  CopyTrader,
  CopyTradingMode,
  CopyVolumeMode,
} from "@/types";

type CopyView = "copy" | "share";
type WizardStep = "account" | "sizing" | "review";

const PREVIEW_TRADERS: CopyTrader[] = [
  {
    id: "00000000-0000-4000-8000-000000000101",
    account_id: "00000000-0000-4000-8000-000000000201",
    owner_user_id: "preview-harbor",
    display_name: "Harbor Strategy",
    description: "Follows market trends with clear entry and exit rules. Trades major forex pairs and gold.",
    is_copyable: true,
    markets: ["EURUSD", "GBPUSD", "XAUUSD"],
    statistics: {
      return_90d_pct: 12.4,
      max_drawdown_pct: -6.3,
      track_record_days: 1260,
      trade_count: 418,
      pending_order_count: 0,
      follower_count: 532,
      data_source: "connected_mt5",
    },
    pending_orders: [],
    stats_updated_at: "2026-07-18T08:15:00Z",
    created_at: "2023-02-01T00:00:00Z",
    updated_at: "2026-07-18T08:15:00Z",
  },
  {
    id: "00000000-0000-4000-8000-000000000102",
    account_id: "00000000-0000-4000-8000-000000000202",
    owner_user_id: "preview-summit",
    display_name: "Summit Markets",
    description: "Trades measured swings across forex and index markets.",
    is_copyable: true,
    markets: ["EURUSD", "USDCAD", "SPX500"],
    statistics: {
      return_90d_pct: 8.7,
      max_drawdown_pct: -4.8,
      track_record_days: 820,
      trade_count: 296,
      pending_order_count: 0,
      follower_count: 318,
      data_source: "connected_mt5",
    },
    pending_orders: [],
    stats_updated_at: "2026-07-18T08:10:00Z",
    created_at: "2024-04-20T00:00:00Z",
    updated_at: "2026-07-18T08:10:00Z",
  },
  {
    id: "00000000-0000-4000-8000-000000000103",
    account_id: "00000000-0000-4000-8000-000000000203",
    owner_user_id: "preview-steady",
    display_name: "Steady Path",
    description: "Uses range-based entries and takes fewer, slower trades.",
    is_copyable: true,
    markets: ["EURUSD", "AUDUSD", "USDJPY"],
    statistics: {
      return_90d_pct: 6.1,
      max_drawdown_pct: -3.9,
      track_record_days: 550,
      trade_count: 184,
      pending_order_count: 0,
      follower_count: 204,
      data_source: "connected_mt5",
    },
    pending_orders: [],
    stats_updated_at: "2026-07-18T08:05:00Z",
    created_at: "2025-01-14T00:00:00Z",
    updated_at: "2026-07-18T08:05:00Z",
  },
];

const PREVIEW_ACCOUNTS: CopyAccount[] = [
  {
    id: "00000000-0000-4000-8000-000000000301",
    legacy_id: "preview-live",
    name: "Live Account",
    status: "active",
    setup_complete: true,
  },
  {
    id: "00000000-0000-4000-8000-000000000302",
    legacy_id: "preview-growth",
    name: "Growth Account",
    status: "active",
    setup_complete: true,
  },
];

const PREVIEW_IMAGES = [
  "/traders/harbor-strategy.webp",
  "/traders/summit-markets.webp",
  "/traders/steady-path.webp",
];

function traderImage(trader: CopyTrader, index: number): string | null {
  if (trader.owner_user_id.startsWith("preview-")) return PREVIEW_IMAGES[index] ?? null;
  return null;
}

function pendingOrderType(type: string): string {
  return type
    .split("_")
    .filter(Boolean)
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

function pendingOrderCountLabel(count: number): string {
  return `${count} pending ${count === 1 ? "order" : "orders"}`;
}

function pendingPrice(value: number | null): string {
  return value && value > 0 ? value.toFixed(value >= 100 ? 2 : 5) : "—";
}

function formatPercent(value: number | null, includePlus = false) {
  if (value === null) return "Not enough history";
  const sign = includePlus && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function trackRecord(days: number) {
  if (days <= 0) return "No closed trades";
  if (days < 31) return `${days} days`;
  if (days < 365) return `${Math.max(1, Math.round(days / 30))} months`;
  const years = days / 365;
  return `${years.toFixed(years >= 2 ? 1 : 0)} years`;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function traderMarketsOverlap(trader: CopyTrader, subscriptions: CopySubscription[]) {
  const activeMarkets = new Set(
    subscriptions
      .filter((item) => item.status === "active" || item.status === "paused")
      .flatMap((item) => item.trader_markets)
  );
  return trader.markets.filter((market) => activeMarkets.has(market));
}

export function CopyTradingClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const {
    account: activeBrokerAccount,
    isConnected: brokerConnected,
  } = useDashboard();
  const preview = searchParams.get("preview") === "1";
  const currentView: CopyView = searchParams.get("view") === "share" ? "share" : "copy";

  const [overview, setOverview] = useState<CopyOverview | null>(null);
  const [traders, setTraders] = useState<CopyTrader[]>(preview ? PREVIEW_TRADERS : []);
  const [selectedTraderId, setSelectedTraderId] = useState<string>(PREVIEW_TRADERS[0].id);
  const [search, setSearch] = useState("");
  const [market, setMarket] = useState("");
  const [historyFilter, setHistoryFilter] = useState("any");
  const [drawdownFilter, setDrawdownFilter] = useState("any");
  const [loading, setLoading] = useState(!preview);
  const [pageError, setPageError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const loadOverview = useCallback(async () => {
    if (preview) {
      setOverview({
        success: true,
        accounts: PREVIEW_ACCOUNTS,
        owned_traders: [],
        subscriptions: [],
        recent_executions: [],
        runtimes: PREVIEW_ACCOUNTS.map((item) => ({
          account_id: item.id,
          status: "healthy" as const,
          trading_enabled: true,
        })),
        live: { feature_enabled: false, requires_country_eligibility: true },
      });
      setLoading(false);
      return;
    }
    try {
      const next = await getCopyOverview();
      setOverview(next);
      setPageError(null);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Copy trading is unavailable");
    } finally {
      setLoading(false);
    }
  }, [preview]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    if (preview) return;
    const refreshDirectory = async () => {
      try {
        const result = await getCopyDirectory({ search, market: market || undefined });
        setTraders(result.traders);
        setSelectedTraderId((current) =>
          result.traders.some((item) => item.id === current)
            ? current
            : result.traders[0]?.id ?? ""
        );
        setPageError(null);
      } catch (error) {
        setPageError(error instanceof Error ? error.message : "Could not load traders");
      }
    };

    const timer = window.setTimeout(
      () => void refreshDirectory(),
      brokerConnected ? 0 : 250
    );
    const interval = brokerConnected
      ? window.setInterval(() => void refreshDirectory(), 15_000)
      : null;
    return () => {
      window.clearTimeout(timer);
      if (interval !== null) window.clearInterval(interval);
    };
  }, [brokerConnected, market, preview, search]);

  const filteredTraders = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return traders.filter((trader) => {
      if (
        normalized &&
        !`${trader.display_name} ${trader.description} ${trader.markets.join(" ")}`
          .toLowerCase()
          .includes(normalized)
      ) {
        return false;
      }
      if (market && !trader.markets.includes(market)) return false;
      if (historyFilter === "6m" && trader.statistics.track_record_days < 180) return false;
      if (historyFilter === "1y" && trader.statistics.track_record_days < 365) return false;
      const drawdown = Math.abs(trader.statistics.max_drawdown_pct ?? 100);
      if (drawdownFilter === "5" && drawdown > 5) return false;
      if (drawdownFilter === "10" && drawdown > 10) return false;
      return true;
    });
  }, [drawdownFilter, historyFilter, market, search, traders]);

  const selectedTrader =
    filteredTraders.find((item) => item.id === selectedTraderId) ?? filteredTraders[0] ?? null;
  const selectedIndex = Math.max(
    0,
    traders.findIndex((item) => item.id === selectedTrader?.id)
  );

  const setView = (view: CopyView) => {
    const next = new URLSearchParams(searchParams.toString());
    if (view === "share") next.set("view", "share");
    else next.delete("view");
    router.replace(`${pathname}${next.size ? `?${next.toString()}` : ""}`, { scroll: false });
  };

  return (
    <div className="mx-auto w-full max-w-[1220px] pb-10">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Copy traders</h1>
          <p className="mt-1 max-w-2xl text-sm text-text-muted">Find someone to copy, then choose your account and loss limits.</p>
        </div>
        {preview && (
          <span className="sr-only">
            Preview data
          </span>
        )}
      </div>

      <div
        className="mb-5 inline-flex rounded-xl border border-border-subtle bg-bg-tertiary/60 p-1"
        role="tablist"
        aria-label="Copy trading views"
      >
        <button
          type="button"
          role="tab"
          aria-selected={currentView === "copy"}
          onClick={() => setView("copy")}
          className={cn(
            "min-w-40 rounded-lg px-5 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            currentView === "copy"
              ? "bg-accent text-white shadow-sm"
              : "text-text-muted hover:text-text-primary"
          )}
        >
          Copy traders
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={currentView === "share"}
          onClick={() => setView("share")}
          className={cn(
            "min-w-40 rounded-lg px-5 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            currentView === "share"
              ? "bg-accent text-white shadow-sm"
              : "text-text-muted hover:text-text-primary"
          )}
        >
          Share my trades
        </button>
      </div>

      {currentView === "copy" ? (
        <CopyTradersView
          traders={filteredTraders}
          selectedTrader={selectedTrader}
          selectedIndex={selectedIndex}
          overview={overview}
          loading={loading}
          error={pageError}
          search={search}
          market={market}
          historyFilter={historyFilter}
          drawdownFilter={drawdownFilter}
          onSearch={setSearch}
          onMarket={setMarket}
          onHistory={setHistoryFilter}
          onDrawdown={setDrawdownFilter}
          onSelect={setSelectedTraderId}
          onStart={() => setWizardOpen(true)}
          onRetry={loadOverview}
          onSubscriptionChange={loadOverview}
        />
      ) : (
        <ShareTradesView overview={overview} loading={loading} onSaved={loadOverview} />
      )}

      {wizardOpen && selectedTrader && overview && (
        <CopyWizard
          trader={selectedTrader}
          accounts={overview.accounts}
          subscriptions={overview.subscriptions}
          liveEnabled={overview.live.feature_enabled}
          accountBalance={preview ? 10_000 : activeBrokerAccount?.balance ?? null}
          preview={preview}
          onClose={() => setWizardOpen(false)}
          onComplete={() => {
            setWizardOpen(false);
            void loadOverview();
          }}
        />
      )}
    </div>
  );
}

function ProgressSteps({ active }: { active: "trader" | WizardStep }) {
  const steps: Array<{ id: "trader" | WizardStep; label: string }> = [
    { id: "trader", label: "Trader" },
    { id: "account", label: "Account" },
    { id: "sizing", label: "Trade size" },
    { id: "review", label: "Review" },
  ];
  const activeIndex = steps.findIndex((item) => item.id === active);
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Copy setup progress">
      {steps.map((step, index) => (
        <li key={step.id} className="flex items-center gap-2 text-xs sm:text-sm">
          <span
            className={cn(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
              index <= activeIndex
                ? "border-accent bg-accent/15 text-accent"
                : "border-border-default text-text-muted"
            )}
            aria-current={index === activeIndex ? "step" : undefined}
          >
            {index < activeIndex ? <Check className="h-3.5 w-3.5" /> : index + 1}
          </span>
          <span className={index <= activeIndex ? "text-text-primary" : "text-text-muted"}>
            {step.label}
          </span>
          {index < steps.length - 1 && (
            <span className="hidden h-px flex-1 bg-border-subtle sm:block" aria-hidden />
          )}
        </li>
      ))}
    </ol>
  );
}

function CopyTradersView({
  traders,
  selectedTrader,
  selectedIndex,
  overview,
  loading,
  error,
  search,
  market,
  historyFilter,
  drawdownFilter,
  onSearch,
  onMarket,
  onHistory,
  onDrawdown,
  onSelect,
  onStart,
  onRetry,
  onSubscriptionChange,
}: {
  traders: CopyTrader[];
  selectedTrader: CopyTrader | null;
  selectedIndex: number;
  overview: CopyOverview | null;
  loading: boolean;
  error: string | null;
  search: string;
  market: string;
  historyFilter: string;
  drawdownFilter: string;
  onSearch: (value: string) => void;
  onMarket: (value: string) => void;
  onHistory: (value: string) => void;
  onDrawdown: (value: string) => void;
  onSelect: (value: string) => void;
  onStart: () => void;
  onRetry: () => Promise<void>;
  onSubscriptionChange: () => Promise<void>;
}) {
  const marketOptions = Array.from(new Set(traders.flatMap((item) => item.markets))).sort();
  return (
    <section role="tabpanel" aria-label="Copy traders">
      <div className="mb-5">
        <ProgressSteps active="trader" />
      </div>

      <div className="mb-4">
        <h2 className="text-2xl font-semibold tracking-tight text-text-primary">
          Find a trader whose approach fits you
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Performance is broker-derived. You decide who to copy; the platform does not rank traders.
        </p>
      </div>

      <div className="mb-4 max-w-xl">
        <label className="sr-only" htmlFor="trader-search">
          Search traders or markets
        </label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            id="trader-search"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search by name or market"
            className="h-12 w-full rounded-xl border border-border-default bg-bg-secondary pl-11 pr-4 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <FilterSelect
            label="Markets"
            value={market}
            onChange={onMarket}
            options={[{ value: "", label: "All markets" }, ...marketOptions.map((item) => ({ value: item, label: item }))]}
            icon={<Globe2 className="h-4 w-4" />}
          />
          <FilterSelect
            label="Trading history"
            value={historyFilter}
            onChange={onHistory}
            options={[
              { value: "any", label: "Any history" },
              { value: "6m", label: "6+ months" },
              { value: "1y", label: "1+ year" },
            ]}
            icon={<CalendarDays className="h-4 w-4" />}
          />
          <FilterSelect
            label="Largest drop"
            value={drawdownFilter}
            onChange={onDrawdown}
            options={[
              { value: "any", label: "Any amount" },
              { value: "5", label: "5% or less" },
              { value: "10", label: "10% or less" },
            ]}
            icon={<TrendingDown className="h-4 w-4" />}
          />
        </div>
      </div>

      {error && !loading ? (
        <div className="rounded-2xl border border-danger/25 bg-danger/5 p-6">
          <div className="flex items-start gap-3">
            <CircleAlert className="mt-0.5 h-5 w-5 text-danger" />
            <div>
              <h3 className="text-sm font-semibold text-text-primary">Copy trading needs attention</h3>
              <p className="mt-1 text-sm text-text-muted">{error}</p>
              <Button className="mt-4" size="sm" onClick={() => void onRetry()}>
                Try again
              </Button>
            </div>
          </div>
        </div>
      ) : loading ? (
        <div className="flex min-h-80 flex-col items-center justify-center gap-4 text-sm text-text-muted">
          <PulseDots />
          Loading traders…
        </div>
      ) : traders.length === 0 ? (
        <div className="rounded-2xl border border-border-subtle bg-bg-secondary/60 px-6 py-14 text-center">
          <UsersRound className="mx-auto h-7 w-7 text-text-muted" />
          <h3 className="mt-4 text-base font-semibold text-text-primary">No traders match this search</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            Clear a filter or check again after more connected traders choose to share their trades.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(420px,1.08fr)]">
          <div className="overflow-hidden rounded-2xl border border-border-subtle bg-bg-secondary/45">
            {traders.map((trader, index) => (
              <TraderRow
                key={trader.id}
                trader={trader}
                index={index}
                selected={trader.id === selectedTrader?.id}
                onSelect={() => onSelect(trader.id)}
              />
            ))}
            <p className="border-t border-border-subtle px-5 py-3 text-xs text-text-muted">
              Showing {traders.length} {traders.length === 1 ? "trader" : "traders"}
            </p>
          </div>
          {selectedTrader && (
            <TraderDetail
              trader={selectedTrader}
              image={traderImage(selectedTrader, selectedIndex)}
              onStart={onStart}
            />
          )}
        </div>
      )}

      {overview && overview.subscriptions.length > 0 && (
        <ActiveCopies
          subscriptions={overview.subscriptions}
          accounts={overview.accounts}
          onChanged={onSubscriptionChange}
        />
      )}
    </section>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  icon,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  icon: ReactNode;
}) {
  return (
    <Select
      aria-label={label}
      value={value}
      onValueChange={onChange}
      options={options}
      leadingIcon={icon}
      compact
      displayValue={
        value && value !== "any"
          ? options.find((option) => option.value === value)?.label
          : label
      }
      containerClassName="w-auto"
      className="min-w-[122px] bg-bg-tertiary/70 text-text-secondary"
      menuClassName="min-w-[190px]"
    />
  );
}

function TraderAvatar({ trader, image, size = "md" }: { trader: CopyTrader; image: string | null; size?: "md" | "lg" }) {
  const dimensions = size === "lg" ? "h-16 w-16" : "h-14 w-14";
  return image ? (
    <Image
      src={image}
      alt=""
      width={size === "lg" ? 64 : 56}
      height={size === "lg" ? 64 : 56}
      className={cn(dimensions, "shrink-0 rounded-full border border-border-default object-cover")}
    />
  ) : (
    <div
      className={cn(
        dimensions,
        "flex shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-elevated text-sm font-semibold text-text-secondary"
      )}
      aria-hidden
    >
      {initials(trader.display_name)}
    </div>
  );
}

function TraderRow({
  trader,
  index,
  selected,
  onSelect,
}: {
  trader: CopyTrader;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const pendingCount = trader.pending_orders?.length ?? 0;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "grid w-full grid-cols-[auto_1fr] items-center gap-4 border-b border-border-subtle px-5 py-4 text-left outline-none last:border-b-0 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent sm:grid-cols-[auto_1fr_auto]",
        selected ? "bg-bg-elevated/80" : "hover:bg-bg-tertiary/40"
      )}
    >
      <TraderAvatar trader={trader} image={traderImage(trader, index)} />
      <span className="min-w-0">
        <span className="flex items-center gap-2">
          <span className="truncate text-base font-semibold text-text-primary">{trader.display_name}</span>
          <BadgeCheck className="h-4 w-4 shrink-0 text-success" aria-label="Connected broker data" />
        </span>
        <span className="mt-1 block truncate text-sm text-text-muted">
          {trader.markets.join(", ") || "No executed markets yet"}
        </span>
        {pendingCount > 0 && (
          <span className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/10 px-2 py-1 text-xs font-medium text-accent">
            <Clock3 className="h-3.5 w-3.5" />
            {pendingOrderCountLabel(pendingCount)}
          </span>
        )}
      </span>
      <span className="col-span-2 grid grid-cols-2 gap-3 text-left sm:col-auto sm:min-w-28 sm:grid-cols-1 sm:gap-2 sm:text-right">
        <span>
          <span className="block text-xs text-text-muted">90-day return</span>
          <span className="text-sm font-semibold text-accent">
            {formatPercent(trader.statistics.return_90d_pct, true)}
          </span>
        </span>
        <span>
          <span className="block text-xs text-text-muted">Largest drop</span>
          <span className="text-sm font-medium text-text-secondary">
            {formatPercent(trader.statistics.max_drawdown_pct)}
          </span>
        </span>
      </span>
    </button>
  );
}

function TraderDetail({ trader, image, onStart }: { trader: CopyTrader; image: string | null; onStart: () => void }) {
  const pendingOrders = trader.pending_orders ?? [];
  const hasPerformanceHistory = trader.statistics.trade_count > 0;
  return (
    <article className="rounded-2xl border border-border-subtle bg-bg-secondary/65 p-5 lg:p-6">
      <div className="flex items-start gap-4">
        <TraderAvatar trader={trader} image={image} size="lg" />
        <div className="min-w-0">
          <h3 className="text-xl font-semibold tracking-tight text-text-primary">{trader.display_name}</h3>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-text-muted">
            Connected broker data <BadgeCheck className="h-4 w-4 text-success" />
          </p>
          <p className="mt-2 max-w-lg text-sm leading-5 text-text-secondary">{trader.description}</p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-4 border-y border-border-subtle py-4">
        <Stat label="90-day return" value={formatPercent(trader.statistics.return_90d_pct, true)} accent />
        <Stat label="Trading history" value={trackRecord(trader.statistics.track_record_days)} />
        <Stat label="Largest drop" value={formatPercent(trader.statistics.max_drawdown_pct)} />
        <Stat label="Markets" value={trader.markets.join(", ") || "None yet"} />
      </dl>

      {pendingOrders.length > 0 && (
        <section className="mt-4 overflow-hidden rounded-xl border border-border-subtle bg-bg-primary/35">
          <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
            <div>
              <h4 className="text-sm font-semibold text-text-primary">Pending orders</h4>
              <p className="mt-0.5 text-xs text-text-muted">
                Waiting for the broker entry price
              </p>
            </div>
            <span className="rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent">
              {pendingOrders.length}
            </span>
          </div>
          <div className="divide-y divide-border-subtle">
            {pendingOrders.map((order, index) => (
              <div
                key={`${order.symbol}-${order.type}-${order.price_open}-${index}`}
                className="px-4 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-text-primary">
                      {order.symbol} · {pendingOrderType(order.type)}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {order.volume.toFixed(2)} lots
                    </p>
                  </div>
                  <p className="text-right text-sm font-medium tabular-nums text-text-primary">
                    {pendingPrice(order.price_open)}
                    <span className="mt-0.5 block text-[11px] font-normal text-text-muted">
                      Entry
                    </span>
                  </p>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-[11px] text-text-muted">Stop loss</dt>
                    <dd className="mt-0.5 text-sm tabular-nums text-danger">
                      {pendingPrice(order.sl)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11px] text-text-muted">Target price</dt>
                    <dd className="mt-0.5 text-sm tabular-nums text-success">
                      {pendingPrice(order.tp)}
                    </dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="mt-4">
        <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          What these numbers mean <Info className="h-3.5 w-3.5 text-text-muted" />
        </h4>
        <p className="mt-2 text-sm leading-5 text-text-muted">
          {pendingOrders.length > 0 && !hasPerformanceHistory
            ? "This trader has pending orders, but no closed-trade performance yet. Pending orders do not affect return or largest drop until they execute and eventually close."
            : "The return covers the last 90 days. Largest drop is the biggest fall from a high point during that period. Past results do not promise future results."}
        </p>
      </div>

      <Button variant="accent" size="lg" className="mt-4" onClick={onStart}>
        <UsersRound className="h-4 w-4" /> Start copying <ArrowRight className="h-4 w-4" />
      </Button>
      <p className="mt-3 flex items-center gap-2 text-xs text-text-muted">
        <LockKeyhole className="h-3.5 w-3.5" /> You will choose your account and loss limits next.
      </p>
    </article>
  );
}

function Stat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className={cn("mt-1 text-lg font-medium", accent ? "text-accent" : "text-text-primary")}>
        {value}
      </dd>
    </div>
  );
}

function CopyWizard({
  trader,
  accounts,
  subscriptions,
  liveEnabled,
  accountBalance,
  preview,
  onClose,
  onComplete,
}: {
  trader: CopyTrader;
  accounts: CopyAccount[];
  subscriptions: CopySubscription[];
  liveEnabled: boolean;
  accountBalance: number | null;
  preview: boolean;
  onClose: () => void;
  onComplete: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const [step, setStep] = useState<WizardStep>("account");
  const [accountId, setAccountId] = useState(accounts.find((item) => item.setup_complete)?.id ?? "");
  const [volumeMode, setVolumeMode] = useState<CopyVolumeMode>("fixed");
  const [fixedVolume, setFixedVolume] = useState("0.01");
  const [dailyLossLimit, setDailyLossLimit] = useState(() =>
    String(accountBalance ? Math.max(1, Math.round(accountBalance) / 100) : 5)
  );
  const [maxOpenTrades, setMaxOpenTrades] = useState("3");
  const [requireStopLoss, setRequireStopLoss] = useState(true);
  const [mode, setMode] = useState<CopyTradingMode>("paper");
  const [overlapAcknowledged, setOverlapAcknowledged] = useState(false);
  const [countryCode, setCountryCode] = useState("");
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedAccount = accounts.find((item) => item.id === accountId);
  const overlapping = traderMarketsOverlap(
    trader,
    subscriptions.filter((item) => item.follower_account_id === accountId)
  );
  const parsedFixedVolume = Number(fixedVolume);
  const parsedDailyLossLimit = Number(dailyLossLimit);
  const parsedMaxOpenTrades = Number(maxOpenTrades);
  const tradeSizeValid =
    volumeMode === "source" ||
    (Number.isFinite(parsedFixedVolume) &&
      parsedFixedVolume >= 0.01 &&
      Math.abs(parsedFixedVolume * 100 - Math.round(parsedFixedVolume * 100)) < 1e-8);
  const protectionValid =
    Number.isFinite(parsedDailyLossLimit) &&
    parsedDailyLossLimit > 0 &&
    Number.isInteger(parsedMaxOpenTrades) &&
    parsedMaxOpenTrades >= 1 &&
    parsedMaxOpenTrades <= 10;

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    const first = dialogRef.current?.querySelector<HTMLElement>("button, input, select, textarea");
    first?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'
        )
      );
      if (!focusable.length) return;
      const firstItem = focusable[0];
      const lastItem = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [onClose]);

  const submit = async () => {
    if (!accountId || !tradeSizeValid || !protectionValid) return;
    setSaving(true);
    setError(null);
    try {
      if (preview) {
        await new Promise((resolve) => window.setTimeout(resolve, 550));
        onComplete();
        return;
      }
      await saveCopyRiskPolicy(accountId, {
        preset: "custom",
        daily_loss_limit_amount: parsedDailyLossLimit,
        max_open_trades: parsedMaxOpenTrades,
        require_stop_loss: requireStopLoss,
        allowed_symbols: trader.markets,
      });
      const created = await createCopySubscription({
        trader_id: trader.id,
        follower_account_id: accountId,
        mode,
        risk_preset: "custom",
        volume_mode: volumeMode,
        fixed_volume: parsedFixedVolume || 0.01,
        overlap_acknowledged: overlapAcknowledged,
        country_code: countryCode || undefined,
        disclosure_version: mode === "live" ? "pending-jurisdiction-pack" : undefined,
      });
      if (mode === "live") {
        await activateLiveCopySubscription(created.subscription.id, {
          country_code: countryCode,
          disclosure_version: "pending-jurisdiction-pack",
          checklist: checks,
        });
      }
      onComplete();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Could not start copying");
    } finally {
      setSaving(false);
    }
  };

  const canContinueFromAccount =
    Boolean(accountId) && (overlapping.length === 0 || overlapAcknowledged);
  const liveChecksComplete =
    mode === "paper" ||
    (["account_connected", "risk_reviewed", "trader_available", "losses_understood"].every(
      (item) => checks[item]
    ) && countryCode.length === 2);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="copy-wizard-title"
        className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-border-default bg-bg-secondary shadow-2xl"
      >
        <div className="sticky top-0 z-10 border-b border-border-subtle bg-bg-secondary/95 px-5 py-4 backdrop-blur-xl sm:px-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-text-muted">Copy {trader.display_name}</p>
              <h2 id="copy-wizard-title" className="mt-1 text-xl font-semibold text-text-primary">
                {step === "account" && "Choose where trades should go"}
                {step === "sizing" && "Choose trade size and protection"}
                {step === "review" && "Review before you start"}
              </h2>
            </div>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-text-muted hover:bg-bg-tertiary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-accent">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-5">
            <ProgressSteps active={step} />
          </div>
        </div>

        <div className="px-5 py-6 sm:px-7">
          {step === "account" && (
            <div className="space-y-3">
              <p className="mb-5 text-sm text-text-muted">Select the MT5 account that should receive copied trades.</p>
              {accounts.length === 0 ? (
                <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 text-sm text-text-secondary">
                  Connect an MT5 account before starting to copy a trader.
                </div>
              ) : (
                accounts.map((item) => (
                  <label key={item.id} className={cn("flex cursor-pointer items-center justify-between rounded-xl border p-4", accountId === item.id ? "border-accent bg-accent/5" : "border-border-subtle hover:border-border-default")}>
                    <span>
                      <span className="block text-sm font-medium text-text-primary">{item.name}</span>
                      <span className="mt-1 block text-xs text-text-muted">{item.setup_complete ? "Connected account" : "Setup not finished"}</span>
                    </span>
                    <input type="radio" name="copy-account" value={item.id} checked={accountId === item.id} onChange={() => setAccountId(item.id)} disabled={!item.setup_complete} className="h-4 w-4 accent-[var(--accent)]" />
                  </label>
                ))
              )}
              {overlapping.length > 0 && (
                <label className="mt-5 flex items-start gap-3 rounded-xl border border-warning/25 bg-warning/5 p-4">
                  <input type="checkbox" checked={overlapAcknowledged} onChange={(event) => setOverlapAcknowledged(event.target.checked)} className="mt-0.5 h-4 w-4 accent-[var(--accent)]" />
                  <span>
                    <span className="block text-sm font-medium text-text-primary">This account already copies the same markets</span>
                    <span className="mt-1 block text-xs leading-5 text-text-muted">{overlapping.join(", ")} could be traded by more than one trader, increasing combined exposure. I understand and want to continue.</span>
                  </span>
                </label>
              )}
            </div>
          )}

          {step === "sizing" && (
            <div className="space-y-6">
              <section aria-labelledby="trade-size-heading">
                <div>
                  <h3 id="trade-size-heading" className="text-sm font-semibold text-text-primary">
                    Trade size
                  </h3>
                  <p className="mt-1 text-sm text-text-muted">
                    Choose how large each copied entry should be on your account.
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setVolumeMode("fixed")}
                    aria-pressed={volumeMode === "fixed"}
                    className={cn(
                      "rounded-xl border p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent",
                      volumeMode === "fixed"
                        ? "border-accent bg-accent/5"
                        : "border-border-subtle hover:border-border-default"
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-text-primary">Fixed lot</span>
                      {volumeMode === "fixed" && <Check className="h-4 w-4 text-accent" />}
                    </span>
                    <span className="mt-2 block text-xs leading-5 text-text-muted">
                      Use one lot size for every copied entry. Best for a small account.
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setVolumeMode("source")}
                    aria-pressed={volumeMode === "source"}
                    className={cn(
                      "rounded-xl border p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent",
                      volumeMode === "source"
                        ? "border-accent bg-accent/5"
                        : "border-border-subtle hover:border-border-default"
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-text-primary">
                        Same as trader
                      </span>
                      {volumeMode === "source" && <Check className="h-4 w-4 text-accent" />}
                    </span>
                    <span className="mt-2 block text-xs leading-5 text-text-muted">
                      Copy the trader&apos;s exact lot size. This can be much larger than 0.01.
                    </span>
                  </button>
                </div>

                {volumeMode === "fixed" && (
                  <div className="mt-4 max-w-xs">
                    <Input
                      label="Lot size per copied trade"
                      type="number"
                      inputMode="decimal"
                      min="0.01"
                      max="100"
                      step="0.01"
                      value={fixedVolume}
                      onChange={(event) => setFixedVolume(event.target.value)}
                      error={
                        tradeSizeValid
                          ? undefined
                          : "Use 0.01 lots or another multiple of 0.01."
                      }
                    />
                  </div>
                )}
                <p className="mt-3 text-xs leading-5 text-text-muted">
                  A trade is skipped if the receiving broker does not support the selected lot
                  size. The platform will not silently resize it.
                </p>
              </section>

              <section
                aria-labelledby="copy-protection-heading"
                className="border-t border-border-subtle pt-5"
              >
                <h3 id="copy-protection-heading" className="text-sm font-semibold text-text-primary">
                  Protection
                </h3>
                <p className="mt-1 text-sm text-text-muted">
                  These limits stop future copied entries. They do not change the selected lot
                  size and apply to every trader copied into this account.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Stop after daily copied loss ($)"
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    step="0.01"
                    value={dailyLossLimit}
                    onChange={(event) => setDailyLossLimit(event.target.value)}
                    error={
                      Number.isFinite(parsedDailyLossLimit) && parsedDailyLossLimit > 0
                        ? undefined
                        : "Enter a daily loss limit."
                    }
                  />
                  <Input
                    label="Maximum open copied trades"
                    type="number"
                    inputMode="numeric"
                    min="1"
                    max="10"
                    step="1"
                    value={maxOpenTrades}
                    onChange={(event) => setMaxOpenTrades(event.target.value)}
                    error={
                      Number.isInteger(parsedMaxOpenTrades) &&
                      parsedMaxOpenTrades >= 1 &&
                      parsedMaxOpenTrades <= 10
                        ? undefined
                        : "Choose between 1 and 10 trades."
                    }
                  />
                </div>
                <label className="mt-4 flex items-start gap-3 rounded-xl border border-border-subtle bg-bg-tertiary/35 p-4">
                  <input
                    type="checkbox"
                    checked={requireStopLoss}
                    onChange={(event) => setRequireStopLoss(event.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-[var(--accent)]"
                  />
                  <span>
                    <span className="block text-sm font-medium text-text-primary">
                      Only copy trades with a stop loss
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-text-muted">
                      Entries without protection will be skipped.
                    </span>
                  </span>
                </label>
              </section>
            </div>
          )}

          {step === "review" && (
            <div className="space-y-5">
              <div className="grid gap-4 rounded-xl border border-border-subtle bg-bg-tertiary/35 p-5 sm:grid-cols-2">
                <Stat label="Trader" value={trader.display_name} />
                <Stat label="Receiving account" value={selectedAccount?.name ?? "Not selected"} />
                <Stat
                  label="Trade size"
                  value={
                    volumeMode === "source"
                      ? "Same as trader"
                      : `${parsedFixedVolume.toFixed(2)} lots per trade`
                  }
                />
                <Stat
                  label="Protection"
                  value={`Stop after $${parsedDailyLossLimit.toFixed(2)} daily loss · ${parsedMaxOpenTrades} open max`}
                />
              </div>
              {volumeMode === "source" && (
                <div className="rounded-xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm leading-5 text-text-secondary">
                  The trader&apos;s lot size may be designed for a much larger account. Copied
                  orders that exceed your broker&apos;s limits will be skipped, but supported
                  orders will use the trader&apos;s full size.
                </div>
              )}

              <fieldset>
                <legend className="text-sm font-semibold text-text-primary">Start in paper or live mode?</legend>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <ModeChoice mode="paper" selected={mode === "paper"} title="Paper copying" description="Follow trades with simulated money. Nothing is sent to your broker." onSelect={() => setMode("paper")} />
                  <ModeChoice mode="live" selected={mode === "live"} title="Live copying" description="Send eligible copied trades to the selected MT5 account." disabled={!liveEnabled} onSelect={() => setMode("live")} />
                </div>
                {!liveEnabled && <p className="mt-2 text-xs text-text-muted">Live copying is safely disabled until this deployment has approved country rules and isolated runtimes.</p>}
              </fieldset>

              {mode === "live" && (
                <div className="rounded-xl border border-warning/25 bg-warning/5 p-5">
                  <h3 className="text-sm font-semibold text-text-primary">Live-copying checklist</h3>
                  <div className="mt-4 space-y-3">
                    {[
                      ["account_connected", "My receiving MT5 account is connected and trading is enabled."],
                      ["risk_reviewed", "I reviewed the trade size and protection settings."],
                      ["trader_available", "I understand this trader can stop sharing at any time."],
                      ["losses_understood", "I understand copied trades can lose real money."],
                    ].map(([key, label]) => (
                      <label key={key} className="flex items-start gap-3 text-sm text-text-secondary"><input type="checkbox" checked={Boolean(checks[key])} onChange={(event) => setChecks((current) => ({ ...current, [key]: event.target.checked }))} className="mt-0.5 h-4 w-4 accent-[var(--accent)]" /><span>{label}</span></label>
                    ))}
                  </div>
                  <div className="mt-4 max-w-xs"><Input label="Country code" placeholder="US" maxLength={2} value={countryCode} onChange={(event) => setCountryCode(event.target.value.toUpperCase())} /></div>
                </div>
              )}
              {error && <div role="alert" className="rounded-xl border border-danger/25 bg-danger/5 px-4 py-3 text-sm text-danger">{error}</div>}
            </div>
          )}
        </div>

        <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-border-subtle bg-bg-secondary/95 px-5 py-4 backdrop-blur-xl sm:px-7">
          <Button variant="ghost" onClick={() => { if (step === "account") onClose(); else setStep(step === "review" ? "sizing" : "account"); }} disabled={saving}>
            {step !== "account" && <ArrowLeft className="h-4 w-4" />}{step === "account" ? "Cancel" : "Back"}
          </Button>
          {step === "account" && <Button variant="accent" onClick={() => setStep("sizing")} disabled={!canContinueFromAccount}>Continue <ArrowRight className="h-4 w-4" /></Button>}
          {step === "sizing" && <Button variant="accent" onClick={() => setStep("review")} disabled={!tradeSizeValid || !protectionValid}>Review <ArrowRight className="h-4 w-4" /></Button>}
          {step === "review" && <Button variant="accent" onClick={() => void submit()} disabled={saving || !liveChecksComplete}>{saving && <IOSSpinner size={16} />}{mode === "live" ? "Start live copying" : "Start paper copying"}</Button>}
        </div>
      </div>
    </div>
  );
}

function ModeChoice({ mode, selected, title, description, disabled = false, onSelect }: { mode: CopyTradingMode; selected: boolean; title: string; description: string; disabled?: boolean; onSelect: () => void }) {
  return (
    <button type="button" onClick={onSelect} disabled={disabled} aria-pressed={selected} className={cn("rounded-xl border p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-45", selected ? "border-accent bg-accent/5" : "border-border-subtle hover:border-border-default")}>
      <span className="flex items-center gap-2 text-sm font-semibold text-text-primary">{mode === "paper" ? <ShieldCheck className="h-4 w-4" /> : <Radio className="h-4 w-4" />}{title}</span>
      <span className="mt-2 block text-xs leading-5 text-text-muted">{description}</span>
    </button>
  );
}

function ActiveCopies({ subscriptions, accounts, onChanged }: { subscriptions: CopySubscription[]; accounts: CopyAccount[]; onChanged: () => Promise<void> }) {
  const [updating, setUpdating] = useState<string | null>(null);
  const toggle = async (subscription: CopySubscription) => {
    setUpdating(subscription.id);
    try {
      await updateCopySubscription(subscription.id, { status: subscription.status === "paused" ? "active" : "paused" });
      await onChanged();
    } finally {
      setUpdating(null);
    }
  };
  return (
    <section className="mt-10 border-t border-border-subtle pt-7" aria-labelledby="active-copies-heading">
      <div className="flex items-center justify-between gap-4">
        <div><h2 id="active-copies-heading" className="text-lg font-semibold text-text-primary">Traders you are copying</h2><p className="mt-1 text-sm text-text-muted">Pause new copied trades without interrupting protective changes or closes.</p></div>
        <span className="rounded-full border border-border-subtle px-3 py-1 text-xs text-text-muted">{subscriptions.length} active</span>
      </div>
      <div className="mt-4 divide-y divide-border-subtle rounded-xl border border-border-subtle bg-bg-secondary/45">
        {subscriptions.map((item) => (
          <div key={item.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-sm font-medium text-text-primary">{item.trader_name}</p><p className="mt-1 text-xs text-text-muted">{accounts.find((account) => account.id === item.follower_account_id)?.name ?? "Trading account"} · {item.mode === "paper" ? "Paper copying" : "Live copying"} · {item.volume_mode === "source" ? "Same lot as trader" : `${(item.fixed_volume ?? 0.01).toFixed(2)} fixed lots`}</p></div>
            <Button size="sm" variant="outline" onClick={() => void toggle(item)} disabled={updating === item.id}>{updating === item.id ? <IOSSpinner size={14} /> : item.status === "paused" ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}{item.status === "paused" ? "Resume" : "Pause new trades"}</Button>
          </div>
        ))}
      </div>
    </section>
  );
}

function ShareTradesView({ overview, loading, onSaved }: { overview: CopyOverview | null; loading: boolean; onSaved: () => Promise<void> }) {
  const [accountId, setAccountId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [isCopyable, setIsCopyable] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const accounts = useMemo(() => overview?.accounts ?? [], [overview?.accounts]);
  const selectedAccountId = accountId || accounts[0]?.id || "";

  useEffect(() => {
    if (!selectedAccountId) return;
    const profile = overview?.owned_traders.find((item) => item.account_id === selectedAccountId);
    const account = accounts.find((item) => item.id === selectedAccountId);
    setDisplayName(profile?.display_name ?? account?.name ?? "");
    setDescription(profile?.description ?? "");
    setIsCopyable(profile?.is_copyable ?? false);
  }, [accounts, overview?.owned_traders, selectedAccountId]);

  const submit = async () => {
    if (!selectedAccountId || !displayName.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      await saveCopyTrader({ account_id: selectedAccountId, display_name: displayName, description, is_copyable: isCopyable });
      setMessage(isCopyable ? "Your trader profile is now searchable." : "Your profile was saved, but copying is turned off.");
      await onSaved();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save your profile");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex min-h-72 flex-col items-center justify-center gap-4 text-sm text-text-muted"><PulseDots /> Loading your accounts…</div>;
  return (
    <section role="tabpanel" aria-label="Share my trades" className="w-full">
      <div className="mb-7 max-w-3xl"><h2 className="text-2xl font-semibold tracking-tight text-text-primary">Let others copy one of your accounts</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">You stay in control. Turning sharing off stops new copied positions while existing copied positions can still receive protective changes and closes.</p></div>
      {accounts.length === 0 ? (
        <div className="rounded-2xl border border-border-subtle bg-bg-secondary/50 p-7"><h3 className="text-base font-semibold text-text-primary">Connect an MT5 account first</h3><p className="mt-2 text-sm text-text-muted">A trader profile can only use broker-derived activity from a connected account.</p></div>
      ) : (
        <div className="rounded-2xl border border-border-subtle bg-bg-secondary/55 p-6 sm:p-7">
          <div className="grid gap-5 lg:grid-cols-2">
            <Select label="MT5 account" value={selectedAccountId} onValueChange={setAccountId} options={accounts.map((item) => ({ value: item.id, label: item.name }))} />
            <Input label="Public trader name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="e.g. Harbor Strategy" />
          </div>
          <div className="mt-5 grid items-stretch gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
            <Textarea className="min-h-28 font-sans" label="Short description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Explain your trading approach in plain language." rows={4} />
            <label className="flex h-full items-start justify-between gap-5 rounded-xl border border-border-subtle p-4"><span><span className="block text-sm font-semibold text-text-primary">Allow others to copy my trades</span><span className="mt-1 block text-xs leading-5 text-text-muted">When enabled, this profile appears in search and new MT5 trades can be copied.</span></span><input type="checkbox" checked={isCopyable} onChange={(event) => setIsCopyable(event.target.checked)} className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]" /></label>
          </div>
          {message && <p role="status" className="mt-4 rounded-lg border border-border-subtle bg-bg-tertiary/40 px-4 py-3 text-sm text-text-secondary">{message}</p>}
          <div className="mt-6 flex justify-end"><Button variant="accent" onClick={() => void submit()} disabled={saving || !displayName.trim()}>{saving && <IOSSpinner size={16} />} Save sharing settings</Button></div>
        </div>
      )}
    </section>
  );
}
