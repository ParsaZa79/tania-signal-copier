"use client";

import { useDashboard } from "@/components/layout/dashboard-layout";
import { OrderForm } from "@/components/orders/order-form";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { formatNumber } from "@/lib/utils";
import { getSymbolPrice, getSymbols, type SymbolListItem } from "@/lib/api";
import { useEffect, useState, useRef, useCallback } from "react";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
}

export default function OrdersPage() {
  const { reconnect } = useDashboard();
  const [symbols, setSymbols] = useState<SymbolListItem[]>([]);
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(true);
  const [isLoadingPrices, setIsLoadingPrices] = useState(true);
  const symbolsRef = useRef<SymbolListItem[]>([]);

  // Fetch symbols from API on mount
  useEffect(() => {
    const fetchSymbols = async () => {
      try {
        const fetchedSymbols = await getSymbols();
        setSymbols(fetchedSymbols);
        symbolsRef.current = fetchedSymbols;
      } catch (error) {
        console.error("Failed to fetch symbols:", error);
      } finally {
        setIsLoadingSymbols(false);
      }
    };
    fetchSymbols();
  }, []);

  const fetchPrices = useCallback(async () => {
    const currentSymbols = symbolsRef.current;
    if (currentSymbols.length === 0) return;

    try {
      const pricePromises = currentSymbols.map(async (s) => {
        try {
          const price = await getSymbolPrice(s.value);
          return { symbol: s.value, data: price };
        } catch {
          return null;
        }
      });

      const results = await Promise.all(pricePromises);
      const priceMap: Record<string, PriceData> = {};

      results.forEach((result) => {
        if (result?.data) {
          priceMap[result.symbol] = result.data;
        }
      });

      setPrices(priceMap);
    } catch (error) {
      console.error("Failed to fetch prices:", error);
    } finally {
      setIsLoadingPrices(false);
    }
  }, []);

  useEffect(() => {
    if (symbols.length === 0) return;
    fetchPrices();
    const interval = setInterval(fetchPrices, 2000);
    return () => clearInterval(interval);
  }, [symbols, fetchPrices]);

  return (
    <PageContainer>
      {/* Page Header */}
      <AnimatedSection>
        <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
          New Order
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Place a new market or pending order
        </p>
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Order Form */}
        <OrderForm onSuccess={reconnect} />

        {/* Live Prices */}
        <Card>
          <CardHeader className="bg-bg-tertiary/30">
            <div className="flex items-center gap-3">
              <CardTitle>Live Prices</CardTitle>
              <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-bg-tertiary">
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-[10px] text-text-muted">Streaming</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoadingSymbols || isLoadingPrices ? (
              <div className="py-16 text-center">
                <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center animate-pulse">
                  <Activity className="w-6 h-6 text-text-muted" />
                </div>
                <p className="text-text-muted">
                  {isLoadingSymbols ? "Loading symbols..." : "Loading prices..."}
                </p>
              </div>
            ) : symbols.length === 0 ? (
              <div className="py-16 text-center">
                <p className="text-text-muted">No symbols available</p>
              </div>
            ) : (
              <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-bg-secondary">
                    <tr className="border-b border-border-subtle">
                      <th className="px-6 py-3 text-left">Symbol</th>
                      <th className="px-6 py-3 text-right">Bid</th>
                      <th className="px-6 py-3 text-right">Ask</th>
                      <th className="px-6 py-3 text-right">Spread</th>
                    </tr>
                  </thead>
                  <tbody>
                    {symbols.map((symbol) => {
                      const price = prices[symbol.value];
                      return (
                        <tr
                          key={symbol.value}
                          className="border-b border-border-subtle last:border-0 group hover:bg-bg-tertiary/30"
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-bg-tertiary flex items-center justify-center">
                                <span className="text-xs font-semibold text-accent">
                                  {symbol.value.slice(0, 2)}
                                </span>
                              </div>
                              <span className="font-medium text-text-primary text-sm">
                                {symbol.label}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <TrendingDown className="w-3 h-3 text-danger" />
                              <span className="text-sm text-danger tabular-nums font-mono">
                                {price ? formatNumber(price.bid, 5) : "-"}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <TrendingUp className="w-3 h-3 text-success" />
                              <span className="text-sm text-success tabular-nums font-mono">
                                {price ? formatNumber(price.ask, 5) : "-"}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <span className="text-sm text-text-secondary tabular-nums">
                              {price ? formatNumber(price.spread, 1) : "-"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
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
