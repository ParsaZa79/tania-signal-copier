"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  RefreshCw,
  ShieldCheck,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { PulseDots } from "@/components/amicro/pulse-dots";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";
import { ModifyDialog } from "@/components/dashboard/modify-dialog";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { PageLoading } from "@/components/layout";
import { LegacyDialog as Dialog } from "@/components/ui/dialog";
import {
  cancelOrder,
  closePosition,
  getAccountInfo,
  getPendingOrders,
  getSymbolInfo,
  modifyPosition,
  type SymbolTradingInfo,
} from "@/lib/api";
import {
  estimateTradeOutcome,
  formatSignedCurrency,
} from "@/lib/trade-estimate";
import { cn, formatCurrency } from "@/lib/utils";
import type { PendingOrder, Position } from "@/types";

const previewPendingOrders: PendingOrder[] = [
  {
    ticket: 2001,
    symbol: "GBPUSD",
    type: "buy_limit",
    volume: 0.03,
    price_open: 1.335,
    sl: 1.329,
    tp: 1.346,
    comment: "Wait for a lower entry",
  },
];

function friendlyMarketName(symbol: string) {
  const normalized = symbol.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (normalized.includes("XAU") || normalized.includes("GOLD")) return "Gold";
  if (normalized.startsWith("EURUSD")) return "Euro / US Dollar";
  if (normalized.startsWith("GBPUSD")) return "British Pound / US Dollar";
  if (normalized.startsWith("USDJPY")) return "US Dollar / Japanese Yen";
  if (/SPX|SP500|US500/.test(normalized)) return "S&P 500";
  return symbol;
}

function formatPrice(value: number | null) {
  if (value === null) return "Waiting…";
  return value >= 100 ? value.toFixed(2) : value.toFixed(5);
}

function formatOptionalPrice(value: number) {
  return value > 0 ? formatPrice(value) : "—";
}

function formatLeverage(value: number | null | undefined) {
  return value && value > 0 ? `1:${Math.round(value)}` : "—";
}

function fullDate() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date());
}

function estimatePendingOrderOutcomes(
  order: PendingOrder,
  symbolInfo: SymbolTradingInfo | null | undefined
) {
  if (!symbolInfo) return { potentialLoss: null, potentialProfit: null };

  const isBuy = order.type.startsWith("buy");
  const common = {
    entryPrice: order.price_open,
    isBuy,
    point: symbolInfo.point,
    tickValue: symbolInfo.trade_tick_value,
    volume: order.volume,
  };
  const rawLoss =
    order.sl > 0
      ? estimateTradeOutcome({ ...common, exitPrice: order.sl })
      : null;
  const rawProfit =
    order.tp > 0
      ? estimateTradeOutcome({ ...common, exitPrice: order.tp })
      : null;

  return {
    potentialLoss: rawLoss !== null && rawLoss < 0 ? rawLoss : null,
    potentialProfit: rawProfit !== null && rawProfit > 0 ? rawProfit : null,
  };
}

export default function PositionsPage() {
  return (
    <Suspense fallback={<PageLoading label="Opening positions…" />}>
      <PositionsPageContent />
    </Suspense>
  );
}

function PositionsPageContent() {
  const searchParams = useSearchParams();
  const { account, positions, reconnect, session, designPreview } = useDashboard();
  const requestedTicket = Number(searchParams.get("ticket"));
  const openedRequestedTicketRef = useRef<number | null>(null);
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>(
    designPreview ? previewPendingOrders : []
  );
  const [pendingSymbolInfo, setPendingSymbolInfo] = useState<
    Record<string, SymbolTradingInfo | null>
  >({});
  const [accountTradingDetails, setAccountTradingDetails] = useState<{
    currency?: string;
    leverage?: number;
  } | null>(
    designPreview
      ? { currency: "USD", leverage: 100 }
      : account
        ? { currency: account.currency, leverage: account.leverage }
        : null
  );
  const [pendingOpen, setPendingOpen] = useState(false);
  const [loadingPending, setLoadingPending] = useState(!designPreview);
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);
  const [savingTicket, setSavingTicket] = useState<number | null>(null);
  const [cancelCandidate, setCancelCandidate] = useState<PendingOrder | null>(null);
  const [cancellingTicket, setCancellingTicket] = useState<number | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const fallbackAccountCurrency = account?.currency;
  const fallbackAccountLeverage = account?.leverage;

  const loadPendingOrders = useCallback(async () => {
    if (designPreview) {
      setPendingOrders(previewPendingOrders);
      setLoadingPending(false);
      return;
    }

    try {
      const orders = await getPendingOrders();
      setPendingOrders(orders);
      setPageError(null);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Pending orders could not be loaded");
    } finally {
      setLoadingPending(false);
    }
  }, [designPreview]);

  useEffect(() => {
    setLoadingPending(!designPreview);
    void loadPendingOrders();
    if (designPreview) return;
    const timer = window.setInterval(loadPendingOrders, 5000);
    return () => window.clearInterval(timer);
  }, [designPreview, loadPendingOrders, session.activeAccountId]);

  const pendingSymbolKey = useMemo(
    () =>
      Array.from(new Set(pendingOrders.map((order) => order.symbol)))
        .sort()
        .join("|"),
    [pendingOrders]
  );

  useEffect(() => {
    let cancelled = false;
    const symbols = pendingSymbolKey ? pendingSymbolKey.split("|") : [];

    if (symbols.length === 0) {
      setPendingSymbolInfo({});
      return () => {
        cancelled = true;
      };
    }

    async function loadPendingSymbolInfo() {
      const entries = await Promise.all(
        symbols.map(async (symbol) => {
          try {
            return [symbol, await getSymbolInfo(symbol)] as const;
          } catch (error) {
            console.error(`Failed to fetch ${symbol} trading info:`, error);
            return [symbol, null] as const;
          }
        })
      );
      if (!cancelled) setPendingSymbolInfo(Object.fromEntries(entries));
    }

    void loadPendingSymbolInfo();
    return () => {
      cancelled = true;
    };
  }, [pendingSymbolKey, session.activeAccountId]);

  useEffect(() => {
    let cancelled = false;

    if (designPreview) {
      setAccountTradingDetails({ currency: "USD", leverage: 100 });
      return () => {
        cancelled = true;
      };
    }

    async function loadAccountTradingDetails() {
      try {
        const details = await getAccountInfo();
        if (!cancelled) {
          setAccountTradingDetails({
            currency: details.currency,
            leverage: details.leverage,
          });
        }
      } catch (error) {
        console.error("Failed to fetch account trading details:", error);
        if (
          !cancelled &&
          (fallbackAccountCurrency || fallbackAccountLeverage)
        ) {
          setAccountTradingDetails({
            currency: fallbackAccountCurrency,
            leverage: fallbackAccountLeverage,
          });
        }
      }
    }

    void loadAccountTradingDetails();
    return () => {
      cancelled = true;
    };
  }, [
    designPreview,
    fallbackAccountCurrency,
    fallbackAccountLeverage,
    session.activeAccountId,
  ]);

  useEffect(() => {
    if (!Number.isFinite(requestedTicket) || requestedTicket <= 0) {
      openedRequestedTicketRef.current = null;
      return;
    }
    if (openedRequestedTicketRef.current === requestedTicket) return;
    const requestedPosition = positions.find((position) => position.ticket === requestedTicket);
    if (!requestedPosition) return;
    openedRequestedTicketRef.current = requestedTicket;
    setSelectedPosition(requestedPosition);
  }, [positions, requestedTicket]);

  const floatingPnL = useMemo(
    () => positions.reduce((sum, position) => sum + position.profit, 0),
    [positions]
  );
  const unprotectedPositions = positions.filter((position) => position.sl <= 0);
  const firstUnprotected = unprotectedPositions[0] ?? null;

  const handleModify = async (sl: number, tp: number) => {
    if (!selectedPosition) return;
    setSavingTicket(selectedPosition.ticket);
    setPageError(null);
    try {
      if (!designPreview) {
        const result = await modifyPosition(selectedPosition.ticket, sl, tp);
        if (!result.success) throw new Error(result.error || "The trade could not be updated");
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 350));
      }
      setSelectedPosition(null);
      reconnect();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "The trade could not be updated");
    } finally {
      setSavingTicket(null);
    }
  };

  const handleClosePosition = async () => {
    if (!selectedPosition) return;
    setSavingTicket(selectedPosition.ticket);
    setPageError(null);
    try {
      if (!designPreview) {
        const result = await closePosition(selectedPosition.ticket);
        if (!result.success) throw new Error(result.error || "The trade could not be closed");
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 350));
      }
      setSelectedPosition(null);
      reconnect();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "The trade could not be closed");
    } finally {
      setSavingTicket(null);
    }
  };

  const handleCancelOrder = async () => {
    if (!cancelCandidate) return;
    setCancellingTicket(cancelCandidate.ticket);
    setPageError(null);
    try {
      if (!designPreview) {
        await cancelOrder(cancelCandidate.ticket);
        await loadPendingOrders();
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 300));
        setPendingOrders((current) =>
          current.filter((order) => order.ticket !== cancelCandidate.ticket)
        );
      }
      setCancelCandidate(null);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "The pending order could not be cancelled");
    } finally {
      setCancellingTicket(null);
    }
  };

  return (
    <PageContainer className="mx-auto max-w-[1320px] space-y-5">
      <AnimatedSection className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-[-0.035em] text-text-primary">Open trades</h1>
          <p className="mt-1.5 text-base text-text-secondary">
            See what is happening and what you can do next.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:items-end">
          <p className="text-sm text-text-muted">{fullDate()}</p>
          {firstUnprotected ? (
            <button
              type="button"
              onClick={() => setSelectedPosition(firstUnprotected)}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-accent-light/25 bg-accent-dark px-5 text-sm font-semibold text-white transition-[background-color,transform,box-shadow] hover:bg-accent hover:text-bg-primary hover:shadow-[0_14px_30px_rgba(91,141,239,0.20)] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-light focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
            >
              <ShieldCheck className="h-4 w-4" />
              Protect the unprotected trade
            </button>
          ) : (
            <button
              type="button"
              onClick={reconnect}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-border-default bg-bg-secondary/45 px-4 text-sm font-medium text-text-secondary hover:bg-bg-tertiary hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          )}
        </div>
      </AnimatedSection>

      {pageError && (
        <AnimatedSection>
          <div role="alert" className="flex items-center gap-3 rounded-xl border border-danger/25 bg-danger/8 px-4 py-3 text-sm text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{pageError}</span>
            <button type="button" onClick={() => setPageError(null)} className="text-xs font-semibold">Dismiss</button>
          </div>
        </AnimatedSection>
      )}

      <AnimatedSection>
        <section className="grid overflow-hidden rounded-[20px] border border-border-default bg-bg-secondary/40 sm:grid-cols-3 sm:divide-x sm:divide-border-subtle">
          <SummaryItem
            icon={Activity}
            label={`${positions.length} open trade${positions.length === 1 ? "" : "s"}`}
            tone="accent"
          />
          <SummaryItem
            icon={TrendingUp}
            eyebrow="Result right now"
            label={`${floatingPnL >= 0 ? "+" : ""}${formatCurrency(floatingPnL)}`}
            tone={floatingPnL >= 0 ? "success" : "danger"}
          />
          <SummaryItem
            icon={AlertTriangle}
            label={`${unprotectedPositions.length} trade${unprotectedPositions.length === 1 ? "" : "s"} need${unprotectedPositions.length === 1 ? "s" : ""} protection`}
            tone={unprotectedPositions.length > 0 ? "warning" : "success"}
          />
        </section>
      </AnimatedSection>

      <AnimatedSection>
        <section className="overflow-hidden rounded-[20px] border border-border-default bg-bg-secondary/40">
          {positions.length === 0 ? (
            <div className="flex min-h-[390px] flex-col items-center justify-center px-6 py-14 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-full border border-border-default bg-bg-tertiary/55 text-text-muted">
                <Activity className="h-6 w-6" />
              </span>
              <h2 className="mt-5 text-xl font-semibold text-text-primary">No open trades right now</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-text-muted">
                When you place a trade or start copying someone, its live result and protection will appear here.
              </p>
              <Link
                href="/copy-trading"
                className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl border border-border-default bg-bg-elevated px-4 text-sm font-medium text-text-primary hover:border-accent/30 hover:bg-bg-tertiary"
              >
                Browse traders to copy
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-border-subtle px-4 sm:px-8">
              {positions.map((position) => (
                <PositionRow
                  key={position.ticket}
                  position={position}
                  onReview={() => setSelectedPosition(position)}
                />
              ))}
            </div>
          )}
        </section>
      </AnimatedSection>

      <AnimatedSection>
        <section className="overflow-hidden rounded-[20px] border border-border-default bg-bg-secondary/40">
          <button
            type="button"
            aria-expanded={pendingOpen}
            onClick={() => setPendingOpen((current) => !current)}
            className="flex min-h-[118px] w-full items-center gap-4 px-5 py-6 text-left transition-colors hover:bg-bg-tertiary/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/60 sm:px-8"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-tertiary/55 text-text-secondary">
              <Clock3 className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="text-base font-semibold text-text-primary">
                Pending orders <span className="font-normal text-text-muted">· {loadingPending ? "Loading" : `${pendingOrders.length} waiting`}</span>
              </span>
              <span className="mt-1 block text-sm text-text-muted">
                A pending order opens only when its chosen price is reached.
              </span>
            </span>
            <ChevronDown className={cn("h-5 w-5 text-text-muted transition-transform", pendingOpen && "rotate-180")} />
          </button>

          {pendingOpen && (
            <div className="border-t border-border-subtle px-5 sm:px-8">
              {loadingPending ? (
                <div className="flex items-center gap-3 py-6 text-sm text-text-muted">
                  <PulseDots />
                  Loading pending orders…
                </div>
              ) : pendingOrders.length === 0 ? (
                <p className="py-6 text-sm text-text-muted">No pending orders are waiting.</p>
              ) : (
                <div className="divide-y divide-border-subtle">
                  {pendingOrders.map((order) => (
                    <PendingOrderRow
                      key={order.ticket}
                      order={order}
                      symbolInfo={pendingSymbolInfo[order.symbol]}
                      accountCurrency={
                        accountTradingDetails?.currency ??
                        account?.currency ??
                        "USD"
                      }
                      accountLeverage={
                        accountTradingDetails?.leverage ?? account?.leverage
                      }
                      onCancel={() => setCancelCandidate(order)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </AnimatedSection>

      <ModifyDialog
        position={selectedPosition}
        isOpen={selectedPosition !== null}
        onClose={() => setSelectedPosition(null)}
        onSubmit={handleModify}
        onClosePosition={handleClosePosition}
        isLoading={savingTicket !== null}
      />

      <Dialog
        isOpen={cancelCandidate !== null}
        onClose={() => setCancelCandidate(null)}
        title="Cancel pending order?"
      >
        <p className="text-sm leading-6 text-text-secondary">
          This removes the instruction to open {cancelCandidate?.symbol}. It does not close any trade that is already open.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={() => setCancelCandidate(null)}
            className="h-10 rounded-xl border border-border-default px-4 text-sm text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
          >
            Keep order
          </button>
          <button
            type="button"
            onClick={handleCancelOrder}
            disabled={cancellingTicket !== null}
            className="h-10 rounded-xl border border-danger/25 bg-danger/10 px-4 text-sm font-medium text-danger hover:bg-danger/20 disabled:opacity-50"
          >
            {cancellingTicket !== null ? "Cancelling…" : "Cancel order"}
          </button>
        </div>
      </Dialog>
    </PageContainer>
  );
}

function PendingOrderRow({
  order,
  symbolInfo,
  accountCurrency,
  accountLeverage,
  onCancel,
}: {
  order: PendingOrder;
  symbolInfo: SymbolTradingInfo | null | undefined;
  accountCurrency: string;
  accountLeverage: number | null | undefined;
  onCancel: () => void;
}) {
  const { potentialLoss, potentialProfit } = estimatePendingOrderOutcomes(
    order,
    symbolInfo
  );

  return (
    <div className="grid gap-5 py-5 xl:grid-cols-[minmax(150px,0.8fr)_minmax(360px,1.7fr)_minmax(220px,1fr)_auto] xl:items-center xl:gap-7">
      <div className="flex min-w-0 items-center gap-3">
        <SymbolIcon symbol={order.symbol} size="lg" className="rounded-full" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text-primary">
            {friendlyMarketName(order.symbol)}{" "}
            <span className="text-text-muted">· {order.symbol}</span>
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        <PendingOrderFact
          label="Opening price"
          value={formatPrice(order.price_open)}
        />
        <PendingOrderFact
          label="Target price"
          value={formatOptionalPrice(order.tp)}
        />
        <PendingOrderFact
          label="Stop loss"
          value={formatOptionalPrice(order.sl)}
        />
        <PendingOrderFact
          label="Leverage"
          value={formatLeverage(accountLeverage)}
        />
      </dl>

      <dl className="grid grid-cols-2 gap-6 xl:min-w-[220px]">
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-muted">
            Potential loss
          </dt>
          <dd
            className={cn(
              "mt-1 text-base font-semibold tabular-nums",
              potentialLoss === null ? "text-text-muted" : "text-danger"
            )}
          >
            {potentialLoss === null
              ? "—"
              : formatSignedCurrency(potentialLoss, accountCurrency)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-muted">
            Potential profit
          </dt>
          <dd
            className={cn(
              "mt-1 text-base font-semibold tabular-nums",
              potentialProfit === null ? "text-text-muted" : "text-success"
            )}
          >
            {potentialProfit === null
              ? "—"
              : formatSignedCurrency(potentialProfit, accountCurrency)}
          </dd>
        </div>
      </dl>

      <button
        type="button"
        onClick={onCancel}
        className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border border-danger/25 bg-danger/8 px-3 text-xs font-medium text-danger hover:bg-danger/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/50"
      >
        <Trash2 className="h-3.5 w-3.5" />
        Cancel order
      </button>
    </div>
  );
}

function PendingOrderFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-muted">
        {label}
      </dt>
      <dd className="mt-1 truncate text-sm font-semibold tabular-nums text-text-primary">
        {value}
      </dd>
    </div>
  );
}

function SummaryItem({
  icon: Icon,
  eyebrow,
  label,
  tone,
}: {
  icon: typeof Activity;
  eyebrow?: string;
  label: string;
  tone: "accent" | "success" | "danger" | "warning";
}) {
  return (
    <div className="flex min-h-[126px] items-center gap-4 border-b border-border-subtle px-5 py-6 last:border-b-0 sm:border-b-0 sm:px-7">
      <Icon
        className={cn(
          "h-7 w-7 shrink-0",
          tone === "accent" && "text-accent",
          tone === "success" && "text-success",
          tone === "danger" && "text-danger",
          tone === "warning" && "text-warning"
        )}
        strokeWidth={1.8}
      />
      <span>
        {eyebrow && <span className="block text-xs text-text-muted">{eyebrow}</span>}
        <span
          className={cn(
            "mt-1 block text-lg font-semibold tabular-nums",
            tone === "accent" && "text-text-primary",
            tone === "success" && "text-success",
            tone === "danger" && "text-danger",
            tone === "warning" && "text-text-primary"
          )}
        >
          {label}
        </span>
      </span>
    </div>
  );
}

function PositionRow({ position, onReview }: { position: Position; onReview: () => void }) {
  const protectedTrade = position.sl > 0;
  const resultTone = position.profit >= 0 ? "text-success" : "text-danger";

  return (
    <article className="grid gap-6 py-9 lg:min-h-[212px] lg:grid-cols-[minmax(190px,0.8fr)_minmax(360px,1.5fr)_minmax(285px,1.1fr)_auto] lg:items-center xl:gap-8">
      <div className="flex items-center gap-4">
        <SymbolIcon
          symbol={position.symbol}
          size="lg"
          className="h-16 w-16 overflow-visible rounded-none border-0 bg-transparent"
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-xl font-semibold text-text-primary">{position.symbol}</h2>
            <span className="text-sm text-text-muted">{friendlyMarketName(position.symbol)}</span>
          </div>
          <p className="mt-2 text-xs text-text-muted">
            {position.volume} lots · Ticket #{position.ticket}
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-4">
        <PriceFact label={position.type === "buy" ? "Bought at" : "Sold at"} value={formatPrice(position.price_open)} />
        <PriceFact label="Current price" value={formatPrice(position.price_current)} />
        <PriceFact
          label="Result right now"
          value={`${position.profit >= 0 ? "+" : ""}${formatCurrency(position.profit)}`}
          className={resultTone}
        />
      </dl>

      <div>
        <div
          className={cn(
            "flex items-center gap-2 text-base font-medium",
            protectedTrade ? "text-success" : "text-warning"
          )}
        >
          {protectedTrade ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
          {protectedTrade ? "Protected with a stop loss" : "No stop loss set"}
        </div>
        <p className="mt-2 max-w-sm text-sm leading-6 text-text-secondary">
          {protectedTrade
            ? `If the price reaches ${formatPrice(position.sl)}, this trade will close automatically.`
            : "This trade can keep losing until you close it."}
        </p>
      </div>

      <button
        type="button"
        onClick={onReview}
        className="inline-flex h-12 items-center justify-center gap-3 rounded-xl border border-border-default bg-bg-elevated/55 px-5 text-sm font-medium text-text-primary transition-colors hover:border-accent/30 hover:bg-bg-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 lg:min-w-[175px]"
      >
        Review trade
        <ChevronRight className="h-4 w-4" />
      </button>
    </article>
  );
}

function PriceFact({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className={cn("mt-2 text-lg font-semibold text-text-primary tabular-nums", className)}>{value}</dd>
    </div>
  );
}

export const positionsPageTestHelpers = {
  estimatePendingOrderOutcomes,
  formatLeverage,
  formatOptionalPrice,
  formatPrice,
  friendlyMarketName,
};
