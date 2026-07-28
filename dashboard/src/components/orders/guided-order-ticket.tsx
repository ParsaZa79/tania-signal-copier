"use client";

import { useMemo, useState } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  placeOrder,
  type SymbolListItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { OrderType, PlaceOrderRequest } from "@/types";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Minus,
  Pencil,
  Plus,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

export interface LivePrice {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  daily_open?: number | null;
  daily_high?: number | null;
  daily_low?: number | null;
  daily_change_percent?: number | null;
}

interface GuidedOrderTicketProps {
  symbols: SymbolListItem[];
  selectedSymbol: string;
  onSymbolChange: (symbol: string) => void;
  price?: LivePrice;
  accountId?: string;
  designPreview?: boolean;
  onSuccess?: () => void;
}

const STEPS = [
  { number: 1, label: "Instrument" },
  { number: 2, label: "Order details" },
  { number: 3, label: "Risk & review" },
];

function quote(value: number | undefined) {
  if (value === undefined) return "—";
  return value.toFixed(value >= 100 ? 2 : 5);
}

function PriceControl({
  label,
  value,
  placeholder,
  step,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  step: number;
  onChange: (value: string) => void;
}) {
  const nudge = (direction: -1 | 1) => {
    const current = Number.parseFloat(value);
    const start = Number.isFinite(current) ? current : Number.parseFloat(placeholder);
    if (!Number.isFinite(start)) return;
    const precision = step >= 0.01 ? 2 : 5;
    onChange(Math.max(0, start + direction * step).toFixed(precision));
  };

  return (
    <div>
      <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-text-secondary">
        {label}
      </label>
      <div className="grid h-11 grid-cols-[1fr_44px_44px] overflow-hidden rounded-xl border border-border-subtle bg-bg-tertiary">
        <input
          aria-label={label}
          type="number"
          step={step}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="min-w-0 bg-transparent px-4 text-sm tabular-nums text-text-primary outline-none placeholder:text-text-muted"
        />
        <button
          type="button"
          onClick={() => nudge(-1)}
          className="flex items-center justify-center border-l border-border-subtle text-text-muted hover:bg-bg-elevated hover:text-text-primary"
          aria-label={`Decrease ${label.toLowerCase()}`}
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => nudge(1)}
          className="flex items-center justify-center border-l border-border-subtle text-text-muted hover:bg-bg-elevated hover:text-text-primary"
          aria-label={`Increase ${label.toLowerCase()}`}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function GuidedOrderTicket({
  symbols,
  selectedSymbol,
  onSymbolChange,
  price,
  designPreview,
  onSuccess,
}: GuidedOrderTicketProps) {
  const [formData, setFormData] = useState({
    order_type: "buy" as OrderType,
    volume: "0.01",
    price: "",
    sl: "",
    tp: "",
  });
  const [reviewOpen, setReviewOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selected = useMemo(
    () => symbols.find((symbol) => symbol.value === selectedSymbol),
    [selectedSymbol, symbols]
  );
  const isBuy = formData.order_type.includes("buy");
  const isPending = formData.order_type !== "buy" && formData.order_type !== "sell";
  const pendingKind = formData.order_type.includes("stop") ? "stop" : "limit";
  const parsedVolume = Number.parseFloat(formData.volume) || 0;
  const troyOunceAmount = parsedVolume * 100;
  const priceStep = (price?.bid ?? 0) >= 100 ? 0.01 : 0.00001;

  const setDirection = (nextIsBuy: boolean) => {
    const nextType: OrderType = isPending
      ? (`${nextIsBuy ? "buy" : "sell"}_${pendingKind}` as OrderType)
      : nextIsBuy
        ? "buy"
        : "sell";
    setFormData((current) => ({ ...current, order_type: nextType }));
    setError(null);
    setSuccess(null);
  };

  const setPendingMode = (pending: boolean) => {
    setFormData((current) => ({
      ...current,
      order_type: pending
        ? (`${isBuy ? "buy" : "sell"}_limit` as OrderType)
        : isBuy
          ? "buy"
          : "sell",
    }));
    setError(null);
    setSuccess(null);
  };

  const changeVolume = (delta: number) => {
    const current = Number.parseFloat(formData.volume) || 0.01;
    const next = Math.max(0.01, Math.round((current + delta) * 100) / 100);
    setFormData((value) => ({ ...value, volume: next.toFixed(2) }));
  };

  const openReview = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (!selectedSymbol || parsedVolume <= 0) {
      setError("Choose a symbol and enter a valid volume.");
      return;
    }
    if (isPending && !formData.price) {
      setError("Enter the price where this pending order should be placed.");
      return;
    }
    setReviewOpen(true);
  };

  const confirmOrder = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const order: PlaceOrderRequest = {
        symbol: selectedSymbol,
        order_type: formData.order_type,
        volume: parsedVolume,
        price: formData.price ? Number.parseFloat(formData.price) : undefined,
        sl: formData.sl ? Number.parseFloat(formData.sl) : undefined,
        tp: formData.tp ? Number.parseFloat(formData.tp) : undefined,
      };

      const result = designPreview
        ? { success: true, ticket: 8412057 }
        : await placeOrder(order);
      if (!result.success) {
        throw new Error(result.error || "The broker did not accept this order.");
      }

      setReviewOpen(false);
      setSuccess(`Order placed successfully · Ticket #${result.ticket}`);
      setFormData((current) => ({ ...current, price: "", sl: "", tp: "" }));
      onSuccess?.();
    } catch (submitError) {
      setReviewOpen(false);
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Could not place the order."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <form onSubmit={openReview} className="min-w-0">
        <ol
          className="mb-8 grid grid-cols-3 gap-3"
          aria-label="Order progress"
        >
          {STEPS.map((step, index) => (
            <li key={step.label} className="flex min-w-0 items-center gap-3">
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm",
                  index === 0
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border-default text-text-muted"
                )}
              >
                {step.number}
              </span>
              <span
                className={cn(
                  "truncate text-sm font-medium",
                  index === 0 ? "text-accent" : "text-text-muted"
                )}
              >
                {step.label}
              </span>
              {index < STEPS.length - 1 && (
                <span className="hidden min-w-6 flex-1 border-t border-border-default lg:block" />
              )}
            </li>
          ))}
        </ol>

        <div className="space-y-5">
          <section aria-labelledby="instrument-label">
            <p
              id="instrument-label"
              className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted"
            >
              Instrument
            </p>
            <div className="flex min-h-16 items-center gap-3 rounded-xl border border-border-subtle bg-bg-secondary/55 px-4 py-3">
              <SymbolIcon symbol={selectedSymbol || "XAUUSD"} size="md" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-medium text-text-primary">
                  {selected?.label || selectedSymbol || "Choose a market"}
                </p>
                <p className="mt-0.5 inline-flex items-center gap-1.5 text-xs text-text-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Market open
                </p>
              </div>
              <Select
                aria-label="Change market"
                options={symbols}
                value={selectedSymbol}
                onValueChange={onSymbolChange}
                displayValue="Change"
                compact
                leadingIcon={<Pencil className="h-3.5 w-3.5" />}
                containerClassName="!w-[132px] shrink-0"
                className="bg-transparent"
              />
            </div>
          </section>

          <section className="border-t border-border-subtle pt-5">
            <p className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
              Direction
            </p>
            <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border-default">
              <button
                type="button"
                onClick={() => setDirection(true)}
                aria-pressed={isBuy}
                className={cn(
                  "flex h-11 items-center justify-center gap-2 rounded-l-[11px] border-r border-border-default text-sm font-medium",
                  isBuy
                    ? "bg-accent/15 text-text-primary ring-1 ring-inset ring-accent/70"
                    : "bg-bg-secondary/45 text-text-secondary hover:bg-bg-tertiary"
                )}
              >
                <TrendingUp
                  className={cn("h-4 w-4", isBuy ? "text-accent" : "text-success")}
                />
                Buy
              </button>
              <button
                type="button"
                onClick={() => setDirection(false)}
                aria-pressed={!isBuy}
                className={cn(
                  "flex h-11 items-center justify-center gap-2 rounded-r-[11px] text-sm font-medium",
                  !isBuy
                    ? "bg-accent/15 text-text-primary ring-1 ring-inset ring-accent/70"
                    : "bg-bg-secondary/45 text-text-secondary hover:bg-bg-tertiary"
                )}
              >
                <TrendingDown
                  className={cn("h-4 w-4", !isBuy ? "text-accent" : "text-danger")}
                />
                Sell
              </button>
            </div>
          </section>

          <section>
            <p className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
              Order type
            </p>
            <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border-default">
              <button
                type="button"
                onClick={() => setPendingMode(false)}
                aria-pressed={!isPending}
                className={cn(
                  "flex h-11 items-center justify-center gap-2 rounded-l-[11px] border-r border-border-default text-sm font-medium",
                  !isPending
                    ? "bg-accent/15 text-text-primary ring-1 ring-inset ring-accent/70"
                    : "bg-bg-secondary/45 text-text-secondary hover:bg-bg-tertiary"
                )}
              >
                <TrendingUp className={cn("h-4 w-4", !isPending && "text-accent")} />
                Market
              </button>
              <button
                type="button"
                onClick={() => setPendingMode(true)}
                aria-pressed={isPending}
                className={cn(
                  "flex h-11 items-center justify-center gap-2 rounded-r-[11px] text-sm font-medium",
                  isPending
                    ? "bg-accent/15 text-text-primary ring-1 ring-inset ring-accent/70"
                    : "bg-bg-secondary/45 text-text-secondary hover:bg-bg-tertiary"
                )}
              >
                <CircleAlert className={cn("h-4 w-4", isPending && "text-accent")} />
                Pending order
              </button>
            </div>

            {isPending && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Select
                  label="Pending type"
                  options={[
                    { value: "limit", label: `${isBuy ? "Buy" : "Sell"} limit` },
                    { value: "stop", label: `${isBuy ? "Buy" : "Sell"} stop` },
                  ]}
                  value={pendingKind}
                  onValueChange={(kind) =>
                    setFormData((current) => ({
                      ...current,
                      order_type: `${isBuy ? "buy" : "sell"}_${kind}` as OrderType,
                    }))
                  }
                />
                <Input
                  label="Entry price"
                  type="number"
                  step="0.00001"
                  value={formData.price}
                  onChange={(event) =>
                    setFormData((current) => ({
                      ...current,
                      price: event.target.value,
                    }))
                  }
                  placeholder={quote(isBuy ? price?.ask : price?.bid)}
                  required
                />
              </div>
            )}
          </section>

          <section>
            <p className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
              Volume (lots)
            </p>
            <div className="grid h-11 grid-cols-[44px_1fr_44px] overflow-hidden rounded-xl border border-border-default bg-bg-secondary/45">
              <button
                type="button"
                onClick={() => changeVolume(-0.01)}
                className="flex items-center justify-center border-r border-border-default text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                aria-label="Decrease volume"
              >
                <Minus className="h-4 w-4" />
              </button>
              <input
                aria-label="Volume in lots"
                type="number"
                min="0.01"
                step="0.01"
                value={formData.volume}
                onChange={(event) =>
                  setFormData((current) => ({
                    ...current,
                    volume: event.target.value,
                  }))
                }
                className="min-w-0 bg-transparent px-4 text-center text-base font-medium tabular-nums text-text-primary outline-none"
                required
              />
              <button
                type="button"
                onClick={() => changeVolume(0.01)}
                className="flex items-center justify-center border-l border-border-default text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                aria-label="Increase volume"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-1.5 text-xs text-text-muted">
              1 lot = 100 troy ounces · {formData.volume || "0"} lots ≈{" "}
              {troyOunceAmount.toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}{" "}
              {troyOunceAmount === 1 ? "troy ounce" : "troy ounces"}
            </p>
          </section>

          <section className="border-t border-border-subtle pt-5">
            <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
              Risk management (optional)
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <PriceControl
                  label="Stop loss (optional)"
                  value={formData.sl}
                  step={priceStep}
                  onChange={(nextValue) =>
                    setFormData((current) => ({
                      ...current,
                      sl: nextValue,
                    }))
                  }
                  placeholder="Price"
                />
                <p className="mt-1.5 text-xs text-text-muted">
                  Limit potential loss on the trade
                </p>
              </div>
              <div>
                <PriceControl
                  label="Take profit (optional)"
                  value={formData.tp}
                  step={priceStep}
                  onChange={(nextValue) =>
                    setFormData((current) => ({
                      ...current,
                      tp: nextValue,
                    }))
                  }
                  placeholder="Price"
                />
                <p className="mt-1.5 text-xs text-text-muted">
                  Lock in profits automatically
                </p>
              </div>
            </div>
          </section>

          {(error || success) && (
            <div
              role="status"
              className={cn(
                "flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm",
                error
                  ? "border-danger/25 bg-danger/[0.07] text-danger"
                  : "border-success/25 bg-success/[0.07] text-success"
              )}
            >
              {error ? (
                <AlertCircle className="h-4 w-4 shrink-0" />
              ) : (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              )}
              {error || success}
            </div>
          )}

          <section aria-labelledby="order-summary-label">
            <p
              id="order-summary-label"
              className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted"
            >
              Order summary
            </p>
            <div className="rounded-xl border border-border-subtle bg-bg-secondary/45 px-4 py-3.5">
              <div className="flex items-start gap-3">
                <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary">
                    {isBuy ? "Buy" : "Sell"} {formData.volume || "0"} lots of{" "}
                    {selectedSymbol || "the selected market"}{" "}
                    {isPending ? `at ${formData.price || "your chosen price"}` : "at market"}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Estimated spread: {price ? `${price.spread} points` : "loading"}
                    {!formData.sl && " · No stop loss set"}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <Button
            type="submit"
            variant="accent"
            size="lg"
            className="h-[52px] w-full bg-[#4f8df7] text-white hover:bg-[#6aa0ff]"
          >
            Review {isBuy ? "buy" : "sell"} order
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </form>

      <Dialog open={reviewOpen} onOpenChange={setReviewOpen}>
        <DialogContent className="max-w-[520px] border-border-default bg-[#111113]">
          <DialogClose onClose={() => setReviewOpen(false)} />
          <DialogHeader className="px-6 py-5">
            <DialogTitle>Review your order</DialogTitle>
            <DialogDescription>
              Check every detail before it is sent to your broker.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 px-6 py-6">
            <div className="flex items-center gap-3">
              <SymbolIcon symbol={selectedSymbol} size="lg" />
              <div>
                <p className="text-base font-medium text-text-primary">
                  {selected?.label || selectedSymbol}
                </p>
                <p className="mt-0.5 text-sm text-text-muted">
                  {isBuy ? "Buy" : "Sell"} ·{" "}
                  {isPending ? formData.order_type.replace("_", " ") : "Market"}
                </p>
              </div>
            </div>

            <dl className="divide-y divide-border-subtle border-y border-border-subtle">
              {[
                ["Volume", `${formData.volume} lots`],
                [
                  "Execution price",
                  isPending
                    ? formData.price
                    : quote(isBuy ? price?.ask : price?.bid),
                ],
                ["Stop loss", formData.sl || "Not set"],
                ["Take profit", formData.tp || "Not set"],
                ["Estimated spread", price ? `${price.spread} points` : "—"],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-center justify-between gap-5 py-3 text-sm"
                >
                  <dt className="text-text-muted">{label}</dt>
                  <dd className="text-right font-medium text-text-primary">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>

            <div className="flex items-start gap-3 rounded-xl border border-accent/20 bg-accent/[0.06] p-4">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <p className="text-sm leading-5 text-text-secondary">
                This confirmation sends a real order to your connected MT5 account.
              </p>
            </div>
          </div>

          <DialogFooter className="px-6 py-5">
            <Button
              type="button"
              variant="outline"
              onClick={() => setReviewOpen(false)}
            >
              Keep editing
            </Button>
            <Button
              type="button"
              onClick={confirmOrder}
              disabled={isLoading}
              className={cn(
                "min-w-[156px] border-0 text-white",
                isBuy
                  ? "bg-success hover:bg-success/90"
                  : "bg-danger hover:bg-danger/90"
              )}
            >
              {isLoading ? (
                <>
                  <IOSSpinner size={16} />
                  Sending…
                </>
              ) : (
                <>Place {isBuy ? "buy" : "sell"} order</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
