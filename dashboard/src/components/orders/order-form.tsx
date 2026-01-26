"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ORDER_TYPES, PENDING_ORDER_TYPES } from "@/lib/constants";
import { placeOrder, getSymbols, type SymbolListItem } from "@/lib/api";
import type { OrderType, PlaceOrderRequest } from "@/types";
import { AlertCircle, CheckCircle, TrendingUp, TrendingDown, Loader2 } from "lucide-react";

interface OrderFormProps {
  onSuccess?: () => void;
}

export function OrderForm({ onSuccess }: OrderFormProps) {
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

  // Fetch symbols on mount
  useEffect(() => {
    const fetchSymbols = async () => {
      try {
        const fetchedSymbols = await getSymbols();
        setSymbols(fetchedSymbols);
        // Set first symbol as default
        if (fetchedSymbols.length > 0) {
          setFormData((prev) =>
            prev.symbol ? prev : { ...prev, symbol: fetchedSymbols[0].value }
          );
        }
      } catch (error) {
        console.error("Failed to fetch symbols:", error);
      } finally {
        setIsLoadingSymbols(false);
      }
    };
    fetchSymbols();
  }, []);

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
        setSuccess(`Order placed successfully! Ticket: ${result.ticket}`);
        // Reset form
        setFormData({
          ...formData,
          price: "",
          sl: "",
          tp: "",
        });
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
    <Card>
      <CardHeader className="bg-bg-tertiary/30">
        <CardTitle>Place New Order</CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Error/Success Messages */}
          {error && (
            <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-danger/20 flex items-center justify-center shrink-0">
                <AlertCircle className="w-4 h-4 text-danger" />
              </div>
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}
          {success && (
            <div className="p-4 rounded-xl bg-success/10 border border-success/20 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-success/20 flex items-center justify-center shrink-0">
                <CheckCircle className="w-4 h-4 text-success" />
              </div>
              <p className="text-sm text-success">{success}</p>
            </div>
          )}

          {/* Symbol */}
          {isLoadingSymbols ? (
            <div className="space-y-2">
              <label className="text-sm text-text-secondary">Symbol</label>
              <div className="h-11 rounded-xl bg-bg-tertiary flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-text-muted animate-spin" />
              </div>
            </div>
          ) : (
            <Select
              label="Symbol"
              options={symbols}
              value={formData.symbol}
              onChange={(e) =>
                setFormData({ ...formData, symbol: e.target.value })
              }
            />
          )}

          {/* Order Type */}
          <Select
            label="Order Type"
            options={ORDER_TYPES}
            value={formData.order_type}
            onChange={(e) =>
              setFormData({
                ...formData,
                order_type: e.target.value as OrderType,
              })
            }
          />

          {/* Volume */}
          <Input
            label="Volume (Lots)"
            type="number"
            step="0.01"
            min="0.01"
            value={formData.volume}
            onChange={(e) =>
              setFormData({ ...formData, volume: e.target.value })
            }
            required
          />

          {/* Price (for pending orders) */}
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
            {/* Stop Loss */}
            <Input
              label="Stop Loss"
              type="number"
              step="0.00001"
              value={formData.sl}
              onChange={(e) => setFormData({ ...formData, sl: e.target.value })}
              placeholder="Optional"
            />

            {/* Take Profit */}
            <Input
              label="Take Profit"
              type="number"
              step="0.00001"
              value={formData.tp}
              onChange={(e) => setFormData({ ...formData, tp: e.target.value })}
              placeholder="Optional"
            />
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className={`w-full h-12 text-sm font-semibold ${
              isBuyOrder
                ? "bg-success hover:bg-success/90 text-white"
                : "bg-danger hover:bg-danger/90 text-white"
            }`}
            disabled={isLoading}
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                <span>Placing Order...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {isBuyOrder ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                <span>
                  Place {formData.order_type.replace("_", " ").toUpperCase()} Order
                </span>
              </div>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
