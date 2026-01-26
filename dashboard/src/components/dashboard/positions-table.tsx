"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PnlBadge } from "./pnl-badge";
import { ModifyDialog } from "./modify-dialog";
import { formatNumber } from "@/lib/utils";
import { closePosition, modifyPosition } from "@/lib/api";
import type { Position } from "@/types";
import { Edit2, X, AlertCircle, TrendingUp, TrendingDown, MoreHorizontal } from "lucide-react";

interface PositionsTableProps {
  positions: Position[];
  onRefresh?: () => void;
}

export function PositionsTable({ positions, onRefresh }: PositionsTableProps) {
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(
    null
  );
  const [isModifyOpen, setIsModifyOpen] = useState(false);
  const [isLoading, setIsLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleModify = async (sl: number, tp: number) => {
    if (!selectedPosition) return;

    setIsLoading(selectedPosition.ticket);
    setError(null);

    try {
      const result = await modifyPosition(selectedPosition.ticket, sl, tp);
      if (!result.success) {
        setError(result.error || "Failed to modify position");
      } else {
        setIsModifyOpen(false);
        onRefresh?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to modify position");
    } finally {
      setIsLoading(null);
    }
  };

  const handleClose = async (ticket: number) => {
    if (!confirm("Are you sure you want to close this position?")) return;

    setIsLoading(ticket);
    setError(null);

    try {
      const result = await closePosition(ticket);
      if (!result.success) {
        setError(result.error || "Failed to close position");
      } else {
        onRefresh?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to close position");
    } finally {
      setIsLoading(null);
    }
  };

  return (
    <>
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between bg-bg-tertiary/30">
          <div className="flex items-center gap-3">
            <CardTitle>Open Positions</CardTitle>
            <Badge variant="accent" size="sm">
              {positions.length} Active
            </Badge>
          </div>
          <Button variant="ghost" size="icon">
            <MoreHorizontal className="w-4 h-4" />
          </Button>
        </CardHeader>

        {error && (
          <div className="mx-6 my-4 p-3 rounded-xl bg-danger/10 border border-danger/20 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-danger/20 flex items-center justify-center shrink-0">
              <AlertCircle className="w-4 h-4 text-danger" />
            </div>
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <CardContent className="p-0">
          {positions.length === 0 ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-bg-tertiary flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-text-secondary mb-1">No open positions</p>
              <p className="text-sm text-text-muted">
                Start trading to see your positions here
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
                    <th className="px-6 py-3 text-right">Entry</th>
                    <th className="px-6 py-3 text-right">Current</th>
                    <th className="px-6 py-3 text-right">SL</th>
                    <th className="px-6 py-3 text-right">TP</th>
                    <th className="px-6 py-3 text-right">P&L</th>
                    <th className="px-6 py-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((position, idx) => (
                    <tr
                      key={position.ticket}
                      className="border-b border-border-subtle last:border-0 group"
                      style={{
                        animationDelay: `${idx * 0.05}s`,
                      }}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-bg-tertiary flex items-center justify-center">
                            <span className="text-xs font-semibold text-accent">
                              {position.symbol.slice(0, 2)}
                            </span>
                          </div>
                          <div>
                            <span className="font-medium text-text-primary text-sm">
                              {position.symbol}
                            </span>
                            <p className="text-[10px] text-text-muted">
                              #{position.ticket}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge
                          variant={
                            position.type === "buy" ? "success" : "danger"
                          }
                          className="gap-1"
                        >
                          {position.type === "buy" ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {position.type.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-primary tabular-nums font-medium">
                          {position.volume}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-secondary tabular-nums font-mono">
                          {formatNumber(position.price_open, 5)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-primary tabular-nums font-mono">
                          {position.price_current
                            ? formatNumber(position.price_current, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            position.sl > 0
                              ? "text-danger"
                              : "text-text-muted"
                          }`}
                        >
                          {position.sl > 0
                            ? formatNumber(position.sl, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            position.tp > 0
                              ? "text-success"
                              : "text-text-muted"
                          }`}
                        >
                          {position.tp > 0
                            ? formatNumber(position.tp, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <PnlBadge value={position.profit} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex justify-center gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => {
                              setSelectedPosition(position);
                              setIsModifyOpen(true);
                            }}
                            disabled={isLoading === position.ticket}
                            className="h-8 w-8"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="danger"
                            onClick={() => handleClose(position.ticket)}
                            disabled={isLoading === position.ticket}
                            className="h-8 w-8"
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modify Dialog */}
      <ModifyDialog
        position={selectedPosition}
        isOpen={isModifyOpen}
        onClose={() => {
          setIsModifyOpen(false);
          setSelectedPosition(null);
        }}
        onSubmit={handleModify}
        isLoading={isLoading !== null}
      />
    </>
  );
}
