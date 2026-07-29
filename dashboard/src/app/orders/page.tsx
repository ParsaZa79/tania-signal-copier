"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Activity, ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { PageHeader, PageLoading } from "@/components/layout";
import { SymbolCell, SymbolIcon } from "@/components/dashboard/symbol-icon";
import {
  GuidedOrderTicket,
  type LivePrice,
} from "@/components/orders/guided-order-ticket";
import { LiveMarketChart } from "@/components/orders/live-market-chart";
import { AnimatedSection, PageContainer } from "@/components/motion";
import {
  getSymbolInfo,
  getSymbolPrice,
  getSymbols,
  type SymbolListItem,
  type SymbolTradingInfo,
} from "@/lib/api";
import { normalizeSymbol } from "@/lib/symbol-icon-resolver";
import { cn } from "@/lib/utils";

const MARKET_PRIORITY = ["XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "BTCUSD"];

function priceDigits(value: number | undefined) {
  if (value === undefined) return 2;
  return value >= 100 ? 2 : 5;
}

function formatPrice(value: number | undefined) {
  if (value === undefined) return "—";
  return value.toFixed(priceDigits(value));
}

function displaySymbol(symbol: string) {
  const normalized = normalizeSymbol(symbol);
  return normalized.length >= 6
    ? `${normalized.slice(0, 3)}/${normalized.slice(3, 6)}`
    : normalized;
}

function findByBase(symbols: SymbolListItem[], base: string) {
  return symbols.find((symbol) => normalizeSymbol(symbol.value).startsWith(base));
}

function selectMarketSymbols(
  symbols: SymbolListItem[],
  selectedSymbol: string
) {
  const selected = symbols.find((symbol) => symbol.value === selectedSymbol);
  const prioritized = MARKET_PRIORITY.map((base) => findByBase(symbols, base));
  const unique = [selected, ...prioritized, ...symbols]
    .filter((symbol): symbol is SymbolListItem => Boolean(symbol))
    .filter(
      (symbol, index, values) =>
        values.findIndex((candidate) => candidate.value === symbol.value) === index
    );
  return unique.slice(0, 5);
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<PageLoading label="Opening order ticket…" />}>
      <OrdersPageContent />
    </Suspense>
  );
}

function OrdersPageContent() {
  const searchParams = useSearchParams();
  const { account, reconnect, session, designPreview } = useDashboard();
  const requestedSymbol = searchParams.get("symbol") ?? undefined;
  const previewChart =
    process.env.NODE_ENV === "development" &&
    searchParams.get("previewChart") === "true";
  const [symbols, setSymbols] = useState<SymbolListItem[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [selectedSymbolInfo, setSelectedSymbolInfo] = useState<
    SymbolTradingInfo | null | undefined
  >(undefined);
  const [prices, setPrices] = useState<Record<string, LivePrice>>({});
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(true);
  const [isLoadingPrices, setIsLoadingPrices] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingSymbols(true);
    setSymbols([]);
    setPrices({});

    async function loadSymbols() {
      try {
        const fetchedSymbols = await getSymbols();
        if (cancelled) return;
        const requested = requestedSymbol
          ? normalizeSymbol(requestedSymbol)
          : undefined;
        const initial =
          (requested
            ? fetchedSymbols.find(
                (symbol) => normalizeSymbol(symbol.value) === requested
              )
            : undefined) ??
          findByBase(fetchedSymbols, "XAUUSD") ??
          fetchedSymbols[0];
        setSymbols(fetchedSymbols);
        setSelectedSymbol(initial?.value ?? "");
      } catch (error) {
        console.error("Failed to fetch symbols:", error);
      } finally {
        if (!cancelled) setIsLoadingSymbols(false);
      }
    }

    void loadSymbols();
    return () => {
      cancelled = true;
    };
  }, [requestedSymbol, session.activeAccountId]);

  const visibleMarkets = useMemo(
    () => selectMarketSymbols(symbols, selectedSymbol),
    [selectedSymbol, symbols]
  );

  const fetchPrices = useCallback(async () => {
    if (visibleMarkets.length === 0) return;
    try {
      const results = await Promise.all(
        visibleMarkets.map(async (symbol) => {
          try {
            return {
              symbol: symbol.value,
              data: await getSymbolPrice(symbol.value),
            };
          } catch (priceError) {
            console.error(`Failed to fetch ${symbol.value} price:`, priceError);
            return null;
          }
        })
      );
      const nextPrices: Record<string, LivePrice> = {};
      for (const result of results) {
        if (result?.data) nextPrices[result.symbol] = result.data;
      }
      setPrices(nextPrices);
    } catch (error) {
      console.error("Failed to fetch prices:", error);
    } finally {
      setIsLoadingPrices(false);
    }
  }, [visibleMarkets]);

  useEffect(() => {
    if (visibleMarkets.length === 0) return;
    setIsLoadingPrices(true);
    void fetchPrices();
    const interval = window.setInterval(fetchPrices, 2_000);
    return () => window.clearInterval(interval);
  }, [fetchPrices, visibleMarkets.length]);

  useEffect(() => {
    let cancelled = false;
    setSelectedSymbolInfo(undefined);

    if (!selectedSymbol) {
      return () => {
        cancelled = true;
      };
    }

    async function loadSymbolInfo() {
      try {
        const info = await getSymbolInfo(selectedSymbol);
        if (!cancelled) setSelectedSymbolInfo(info);
      } catch (error) {
        console.error(`Failed to fetch ${selectedSymbol} trading info:`, error);
        if (!cancelled) setSelectedSymbolInfo(null);
      }
    }

    void loadSymbolInfo();
    return () => {
      cancelled = true;
    };
  }, [selectedSymbol, session.activeAccountId]);

  if (isLoadingSymbols) {
    return <PageLoading label="Opening order ticket…" />;
  }

  const selectedPrice = prices[selectedSymbol];
  const selectedLabel =
    symbols.find((symbol) => symbol.value === selectedSymbol)?.label ??
    selectedSymbol;

  return (
    <PageContainer className="mx-auto max-w-[1380px] space-y-5 pb-8">
      <AnimatedSection>
        <PageHeader
          title="New order"
          description="Place a market or pending order"
        />
      </AnimatedSection>

      <AnimatedSection className="grid min-w-0 gap-8 xl:grid-cols-[minmax(0,1.12fr)_minmax(430px,0.88fr)] xl:gap-0 xl:divide-x xl:divide-border-subtle">
        <div className="min-w-0 xl:pr-7">
          <GuidedOrderTicket
            symbols={symbols}
            selectedSymbol={selectedSymbol}
            onSymbolChange={setSelectedSymbol}
            price={selectedPrice}
            symbolInfo={selectedSymbolInfo}
            accountCurrency={account?.currency ?? "USD"}
            accountId={session.activeAccountId ?? undefined}
            designPreview={designPreview}
            onSuccess={reconnect}
          />
        </div>

        <MarketContext
          selectedSymbol={selectedSymbol}
          selectedLabel={selectedLabel}
          selectedPrice={selectedPrice}
          visibleMarkets={visibleMarkets}
          prices={prices}
          isLoading={isLoadingPrices}
          previewChart={previewChart}
          onSelectMarket={setSelectedSymbol}
        />
      </AnimatedSection>
    </PageContainer>
  );
}

function MarketContext({
  selectedSymbol,
  selectedLabel,
  selectedPrice,
  visibleMarkets,
  prices,
  isLoading,
  previewChart,
  onSelectMarket,
}: {
  selectedSymbol: string;
  selectedLabel: string;
  selectedPrice?: LivePrice;
  visibleMarkets: SymbolListItem[];
  prices: Record<string, LivePrice>;
  isLoading: boolean;
  previewChart: boolean;
  onSelectMarket: (symbol: string) => void;
}) {
  const nearbyMarkets = visibleMarkets.filter(
    (symbol) => symbol.value !== selectedSymbol
  );
  const dailyLow =
    selectedPrice?.daily_low ??
    (previewChart && selectedPrice ? selectedPrice.bid * 0.9975 : undefined);
  const dailyHigh =
    selectedPrice?.daily_high ??
    (previewChart && selectedPrice ? selectedPrice.bid * 1.0015 : undefined);
  const dailyPosition =
    selectedPrice && dailyLow !== undefined && dailyLow !== null &&
    dailyHigh !== undefined && dailyHigh !== null && dailyHigh > dailyLow
      ? Math.min(
          100,
          Math.max(
            0,
            ((selectedPrice.bid - dailyLow) / (dailyHigh - dailyLow)) * 100
          )
        )
      : 50;

  return (
    <aside className="min-w-0 xl:pl-7">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <SymbolIcon symbol={selectedSymbol} size="lg" />
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-lg font-semibold text-text-primary">
              <span className="truncate">{displaySymbol(selectedSymbol)}</span>
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success" />
                Live
              </span>
            </p>
            <p className="mt-0.5 truncate text-xs text-text-muted">
              {selectedLabel}
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-secondary/50 px-2.5 py-1.5 text-[11px] text-text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          Streaming
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 items-end gap-4">
        <div>
          <p className="text-3xl font-medium tracking-[-0.03em] text-text-primary tabular-nums">
            {formatPrice(selectedPrice?.bid)}
          </p>
          <p className="mt-1 text-sm text-text-muted">Bid</p>
        </div>
        <div className="text-center">
          <p className="inline-flex rounded-lg border border-border-subtle bg-bg-secondary/60 px-3 py-1 text-base font-medium tabular-nums text-text-secondary">
            {selectedPrice?.spread ?? "—"}
          </p>
          <p className="mt-1.5 text-xs text-text-muted">Spread (pts)</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-medium tracking-[-0.03em] text-text-primary tabular-nums">
            {formatPrice(selectedPrice?.ask)}
          </p>
          <p className="mt-1 text-sm text-text-muted">Ask</p>
        </div>
      </div>

      <div className="mt-6">
        <LiveMarketChart symbol={selectedSymbol} />
      </div>

      <div className="mt-4 border-b border-border-subtle pb-5">
        <div className="mb-2 flex items-center justify-between text-xs text-text-muted">
          <span>Day range</span>
          <span>
            {selectedPrice?.daily_change_percent === undefined ||
            selectedPrice.daily_change_percent === null
              ? "—"
              : `${selectedPrice.daily_change_percent >= 0 ? "+" : ""}${selectedPrice.daily_change_percent.toFixed(2)}%`}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-16 text-xs tabular-nums text-text-secondary">
            {formatPrice(dailyLow ?? undefined)}
          </span>
          <div className="relative h-1 flex-1 rounded-full bg-bg-elevated">
            <span
              className="absolute inset-y-0 left-0 rounded-full bg-accent"
              style={{ width: `${dailyPosition}%` }}
            />
            <span
              className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg-primary bg-text-primary"
              style={{ left: `${dailyPosition}%` }}
            />
          </div>
          <span className="w-16 text-right text-xs tabular-nums text-text-secondary">
            {formatPrice(dailyHigh ?? undefined)}
          </span>
        </div>
      </div>

      <section className="mt-5" aria-labelledby="nearby-markets-title">
        <div className="mb-2.5 flex items-center justify-between">
          <p
            id="nearby-markets-title"
            className="text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted"
          >
            Nearby markets
          </p>
          <span className="text-[11px] text-text-muted">Live bid / ask</span>
        </div>

        <div className="overflow-hidden rounded-xl border border-border-subtle">
          <div className="grid grid-cols-[minmax(0,1.15fr)_0.65fr_0.65fr_0.55fr] gap-3 border-b border-border-subtle bg-bg-secondary/55 px-3 py-2 text-[10px] font-medium uppercase tracking-[0.08em] text-text-muted">
            <span>Symbol</span>
            <span className="text-right">Bid</span>
            <span className="text-right">Ask</span>
            <span className="text-right">Change</span>
          </div>

          {isLoading && nearbyMarkets.length === 0 ? (
            <div className="flex min-h-28 items-center justify-center gap-2 text-sm text-text-muted">
              <Activity className="h-4 w-4 animate-pulse" />
              Loading markets…
            </div>
          ) : (
            nearbyMarkets.map((symbol) => {
              const price = prices[symbol.value];
              const change = price?.daily_change_percent;
              const positive = change !== undefined && change !== null && change >= 0;
              return (
                <button
                  key={symbol.value}
                  type="button"
                  onClick={() => onSelectMarket(symbol.value)}
                  className="grid w-full grid-cols-[minmax(0,1.15fr)_0.65fr_0.65fr_0.55fr] items-center gap-3 border-b border-border-subtle px-3 py-3 text-left last:border-b-0 hover:bg-bg-secondary/55"
                >
                  <SymbolCell
                    symbol={symbol.value}
                    label={symbol.label}
                    size="sm"
                  />
                  <span className="text-right text-xs tabular-nums text-text-secondary">
                    {formatPrice(price?.bid)}
                  </span>
                  <span className="text-right text-xs tabular-nums text-text-secondary">
                    {formatPrice(price?.ask)}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center justify-end gap-1 text-xs tabular-nums",
                      change === undefined || change === null
                        ? "text-text-muted"
                        : positive
                          ? "text-success"
                          : "text-danger"
                    )}
                  >
                    {change === undefined || change === null ? (
                      "—"
                    ) : (
                      <>
                        {positive ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {Math.abs(change).toFixed(2)}%
                      </>
                    )}
                  </span>
                </button>
              );
            })
          )}
        </div>
        <Link
          href="/analysis"
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:text-accent-light"
        >
          View more markets
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </section>
    </aside>
  );
}
