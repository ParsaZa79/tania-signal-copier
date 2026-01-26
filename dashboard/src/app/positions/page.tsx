"use client";

import { useDashboard } from "@/components/layout/dashboard-layout";
import { PositionsTable } from "@/components/dashboard/positions-table";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getPendingOrders, cancelOrder } from "@/lib/api";
import type { PendingOrder } from "@/types";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { X, RefreshCw, Clock, TrendingUp, TrendingDown } from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

export default function PositionsPage() {
  const { positions, reconnect } = useDashboard();
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [isLoadingPending, setIsLoadingPending] = useState(true);

  const fetchPendingOrders = async () => {
    try {
      const orders = await getPendingOrders();
      setPendingOrders(orders);
    } catch (error) {
      console.error("Failed to fetch pending orders:", error);
    } finally {
      setIsLoadingPending(false);
    }
  };

  useEffect(() => {
    fetchPendingOrders();
    const interval = setInterval(fetchPendingOrders, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCancelOrder = async (ticket: number) => {
    if (!confirm("Are you sure you want to cancel this order?")) return;

    try {
      await cancelOrder(ticket);
      fetchPendingOrders();
    } catch (error) {
      console.error("Failed to cancel order:", error);
    }
  };

  return (
    <PageContainer>
      {/* Page Header */}
      <AnimatedSection className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
            Positions
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Manage your open positions and pending orders
          </p>
        </div>
        <Button variant="outline" onClick={reconnect}>
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </AnimatedSection>

      {/* Open Positions */}
      <AnimatedSection>
        <PositionsTable positions={positions} onRefresh={reconnect} />
      </AnimatedSection>

      {/* Pending Orders */}
      <AnimatedSection>
        <Card>
        <CardHeader className="flex flex-row items-center justify-between bg-bg-tertiary/30">
          <div className="flex items-center gap-3">
            <CardTitle>Pending Orders</CardTitle>
            <Badge variant="default" size="sm">
              {pendingOrders.length} Pending
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoadingPending ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center animate-pulse">
                <Clock className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-text-muted">Loading pending orders...</p>
            </div>
          ) : pendingOrders.length === 0 ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center">
                <Clock className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-text-secondary mb-1">No pending orders</p>
              <p className="text-sm text-text-muted">
                Create a limit or stop order to see it here
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
                    <th className="px-6 py-3 text-right">Price</th>
                    <th className="px-6 py-3 text-right">SL</th>
                    <th className="px-6 py-3 text-right">TP</th>
                    <th className="px-6 py-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingOrders.map((order) => (
                    <tr
                      key={order.ticket}
                      className="border-b border-border-subtle last:border-0 group"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-bg-tertiary flex items-center justify-center">
                            <span className="text-xs font-semibold text-accent">
                              {order.symbol.slice(0, 2)}
                            </span>
                          </div>
                          <span className="font-medium text-text-primary text-sm">
                            {order.symbol}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge
                          variant={
                            order.type.includes("buy") ? "info" : "warning"
                          }
                          className="gap-1"
                        >
                          {order.type.includes("buy") ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {order.type.replace("_", " ").toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-primary tabular-nums font-medium">
                          {order.volume}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-secondary tabular-nums font-mono">
                          {order.price_open.toFixed(5)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            order.sl > 0
                              ? "text-danger"
                              : "text-text-muted"
                          }`}
                        >
                          {order.sl > 0 ? order.sl.toFixed(5) : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            order.tp > 0
                              ? "text-success"
                              : "text-text-muted"
                          }`}
                        >
                          {order.tp > 0 ? order.tp.toFixed(5) : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <Button
                          size="icon"
                          variant="danger"
                          onClick={() => handleCancelOrder(order.ticket)}
                          className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="w-3.5 h-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
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
