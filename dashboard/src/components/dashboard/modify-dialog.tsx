"use client";

import { useState } from "react";
import { LegacyDialog as Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Position } from "@/types";
import { TrendingUp, TrendingDown, Target, Shield } from "lucide-react";

interface ModifyDialogProps {
  position: Position | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (sl: number, tp: number) => Promise<void>;
  isLoading?: boolean;
}

// Inner form component that resets state when position changes via key
function ModifyForm({
  position,
  onClose,
  onSubmit,
  isLoading,
}: Omit<ModifyDialogProps, "isOpen">) {
  const [sl, setSl] = useState(
    position?.sl && position.sl > 0 ? position.sl.toString() : ""
  );
  const [tp, setTp] = useState(
    position?.tp && position.tp > 0 ? position.tp.toString() : ""
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(parseFloat(sl) || 0, parseFloat(tp) || 0);
  };

  if (!position) return null;

  const isBuy = position.type === "buy";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Position Info */}
      <div className="p-4 rounded-xl bg-bg-tertiary border border-border-subtle">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
            <span className="text-sm font-bold text-accent">
              {position.symbol.slice(0, 2)}
            </span>
          </div>
          <div>
            <p className="font-semibold text-text-primary">{position.symbol}</p>
            <p className="text-xs text-text-muted">#{position.ticket}</p>
          </div>
          <Badge variant={isBuy ? "success" : "danger"} className="ml-auto gap-1">
            {isBuy ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {position.type.toUpperCase()}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-bg-elevated">
            <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Volume</p>
            <p className="text-sm font-medium text-text-primary tabular-nums">{position.volume}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-elevated">
            <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Entry Price</p>
            <p className="text-sm font-medium text-text-primary tabular-nums font-mono">
              {position.price_open.toFixed(5)}
            </p>
          </div>
        </div>
      </div>

      {/* SL/TP Inputs */}
      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-md bg-danger/10 border border-danger/20 flex items-center justify-center">
              <Shield className="w-3 h-3 text-danger" />
            </div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
              Stop Loss
            </label>
          </div>
          <input
            type="number"
            step="0.00001"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            placeholder="Enter stop loss price"
            className="w-full h-11 px-4 rounded-xl border bg-bg-tertiary text-text-primary text-sm tabular-nums border-border-subtle placeholder:text-text-muted focus:outline-none focus:border-danger/50 focus:ring-1 focus:ring-danger/20 transition-colors duration-200"
          />
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-md bg-success/10 border border-success/20 flex items-center justify-center">
              <Target className="w-3 h-3 text-success" />
            </div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
              Take Profit
            </label>
          </div>
          <input
            type="number"
            step="0.00001"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            placeholder="Enter take profit price"
            className="w-full h-11 px-4 rounded-xl border bg-bg-tertiary text-text-primary text-sm tabular-nums border-border-subtle placeholder:text-text-muted focus:outline-none focus:border-success/50 focus:ring-1 focus:ring-success/20 transition-colors duration-200"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          className="flex-1"
          onClick={onClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="accent"
          className="flex-1"
          disabled={isLoading}
        >
          {isLoading ? (
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-bg-primary/30 border-t-bg-primary animate-spin" />
              <span>Saving...</span>
            </div>
          ) : (
            "Save Changes"
          )}
        </Button>
      </div>
    </form>
  );
}

export function ModifyDialog({
  position,
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}: ModifyDialogProps) {
  if (!position) return null;

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title="Modify Position">
      {/* Use key to reset form state when position changes */}
      <ModifyForm
        key={position.ticket}
        position={position}
        onClose={onClose}
        onSubmit={onSubmit}
        isLoading={isLoading}
      />
    </Dialog>
  );
}
