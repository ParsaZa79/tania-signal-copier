"use client";

import { useState, useEffect } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { PulseDots } from "@/components/amicro/pulse-dots";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  SectionPanel,
  PanelHeader,
  PanelBody,
} from "@/components/layout";
import { ORDER_TYPES, PENDING_ORDER_TYPES } from "@/lib/constants";
import { placeOrder, getSymbols, type SymbolListItem } from "@/lib/api";
import type { OrderType, PlaceOrderRequest } from "@/types";
import {
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

interface OrderFormProps {
  onSuccess?: () => void;
  accountId?: string;
  initialSymbol?: string;
}

export function OrderForm({ onSuccess, accountId, initialSymbol }: OrderFormProps) {
  const [symbols, setSymbols] = useState<SymbolListItem[]>([]);
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(true);
  const [formData, setFormData] = useState({
    symbol: "",
    order_type: "buy" as OrderType,
    volume: "0.01",
    price: "",
    sl: "",
    tp: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const isPendingOrder = PENDING_ORDER_TYPES.includes(formData.order_type);
  const isBuyOrder = formData.order_type.includes("buy");

  useEffect(() => {
    setIsLoadingSymbols(true);
    setSymbols([]);
    const fetchSymbols = async () => {
      try {
        const fetchedSymbols = await getSymbols();
        setSymbols(fetchedSymbols);
        if (fetchedSymbols.length > 0) {
          const requested = initialSymbol?.toUpperCase().replace(/[^A-Z0-9]/g, "");
          const initialMatch = requested
            ? fetchedSymbols.find(
                (symbol) => symbol.value.toUpperCase().replace(/[^A-Z0-9]/g, "") === requested
              )
            : undefined;
          setFormData((prev) => ({
            ...prev,
            symbol: initialMatch?.value ?? (prev.symbol || fetchedSymbols[0].value),
          }));
        }
      } catch (err) {
        console.error("Failed to fetch symbols:", err);
      } finally {
        setIsLoadingSymbols(false);
      }
    };
    fetchSymbols();
  }, [accountId, initialSymbol]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const order: PlaceOrderRequest = {
        symbol: formData.symbol,
        order_type: formData.order_type,
        volume: parseFloat(formData.volume),
        price: formData.price ? parseFloat(formData.price) : undefined,
        sl: formData.sl ? parseFloat(formData.sl) : undefined,
        tp: formData.tp ? parseFloat(formData.tp) : undefined,
      };

      const result = await placeOrder(order);

      if (result.success) {
        setSuccess(`Order placed successfully. Ticket: ${result.ticket}`);
        setFormData({ ...formData, price: "", sl: "", tp: "" });
        onSuccess?.();
      } else {
        setError(result.error || "Failed to place order");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to place order");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SectionPanel>
      <PanelHeader
        eyebrow="Execution"
        title="Place order"
        description="Market or pending order with optional SL/TP"
      />
      <PanelBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 flex items-center gap-3">
              <AlertCircle className="w-4 h-4 text-danger shrink-0" />
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}
          {success && (
            <div className="p-4 rounded-xl bg-success/10 border border-success/20 flex items-center gap-3">
              <CheckCircle className="w-4 h-4 text-success shrink-0" />
              <p className="text-sm text-success">{success}</p>
            </div>
          )}

          {isLoadingSymbols ? (
            <div className="space-y-2">
              <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                Symbol
              </label>
              <div className="h-11 rounded-xl bg-bg-tertiary border border-border-subtle flex items-center justify-center">
                <PulseDots />
              </div>
            </div>
          ) : (
            <Select
              label="Symbol"
              options={symbols}
              value={formData.symbol}
              onValueChange={(nextValue) =>
                setFormData({ ...formData, symbol: nextValue })
              }
            />
          )}

          <Select
            label="Order type"
            options={ORDER_TYPES}
            value={formData.order_type}
            onValueChange={(nextValue) =>
              setFormData({
                ...formData,
                order_type: nextValue as OrderType,
              })
            }
          />

          <Input
            label="Volume (lots)"
            type="number"
            step="0.01"
            min="0.01"
            value={formData.volume}
            onChange={(e) =>
              setFormData({ ...formData, volume: e.target.value })
            }
            required
          />

          {isPendingOrder && (
            <Input
              label="Price"
              type="number"
              step="0.00001"
              value={formData.price}
              onChange={(e) =>
                setFormData({ ...formData, price: e.target.value })
              }
              required
              placeholder="Entry price for pending order"
            />
          )}

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Stop loss"
              type="number"
              step="0.00001"
              value={formData.sl}
              onChange={(e) => setFormData({ ...formData, sl: e.target.value })}
              placeholder="Optional"
            />
            <Input
              label="Take profit"
              type="number"
              step="0.00001"
              value={formData.tp}
              onChange={(e) => setFormData({ ...formData, tp: e.target.value })}
              placeholder="Optional"
            />
          </div>

          <Button
            type="submit"
            className={`w-full h-12 text-sm font-semibold ${
              isBuyOrder
                ? "bg-success hover:opacity-90 text-white border-0"
                : "bg-danger hover:opacity-90 text-white border-0"
            }`}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <IOSSpinner size={16} />
                Placing order…
              </span>
            ) : (
              <span className="flex items-center gap-2">
                {isBuyOrder ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                Place {formData.order_type.replace("_", " ").toUpperCase()}
              </span>
            )}
          </Button>
        </form>
      </PanelBody>
    </SectionPanel>
  );
}
