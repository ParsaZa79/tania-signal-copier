"use client";

import { useState } from "react";
import { IOSSpinner } from "@/components/amicro/ios-spinner";
import { LegacyDialog as Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Position } from "@/types";
import { SymbolIcon } from "./symbol-icon";
import { TrendingUp, TrendingDown, Target, Shield } from "lucide-react";

interface ModifyDialogProps {
  position: Position | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (sl: number, tp: number) => Promise<void>;
  onClosePosition?: () => Promise<void>;
  isLoading?: boolean;
}

// Inner form component that resets state when position changes via key
function ModifyForm({
  position,
  onClose,
  onSubmit,
  onClosePosition,
  isLoading,
}: Omit<ModifyDialogProps, "isOpen">) {
  const [sl, setSl] = useState(
    position?.sl && position.sl > 0 ? position.sl.toString() : ""
  );
  const [tp, setTp] = useState(
    position?.tp && position.tp > 0 ? position.tp.toString() : ""
  );
  const [confirmingClose, setConfirmingClose] = useState(false);

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
          <SymbolIcon symbol={position.symbol} size="lg" />
          <div>
            <p className="font-semibold text-text-primary">{position.symbol}</p>
            <p className="text-xs text-text-muted">Trade #{position.ticket}</p>
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
            <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Trade size</p>
            <p className="text-sm font-medium text-text-primary tabular-nums">{position.volume} lots</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-elevated">
            <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Opening price</p>
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
              Automatic loss limit <span className="normal-case text-text-muted">(stop loss)</span>
            </label>
          </div>
          <input
            type="number"
            step="0.00001"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            placeholder="Price where this trade should close"
            className="w-full h-11 px-4 rounded-xl border bg-bg-tertiary text-text-primary text-sm tabular-nums border-border-subtle placeholder:text-text-muted focus:outline-none focus:border-danger/50 focus:ring-1 focus:ring-danger/20 transition-colors duration-200"
          />
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-md bg-success/10 border border-success/20 flex items-center justify-center">
              <Target className="w-3 h-3 text-success" />
            </div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
              Automatic profit target <span className="normal-case text-text-muted">(take profit)</span>
            </label>
          </div>
          <input
            type="number"
            step="0.00001"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            placeholder="Price where profit should be taken"
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
              <IOSSpinner size={16} />
              <span>Saving...</span>
            </div>
          ) : (
            "Save protection"
          )}
        </Button>
      </div>

      {onClosePosition && (
        <div className="border-t border-border-subtle pt-4">
          {confirmingClose ? (
            <div className="rounded-xl border border-danger/25 bg-danger/8 p-4">
              <p className="text-sm font-medium text-text-primary">Close this trade now?</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                Your broker will close it at the next available market price.
              </p>
              <div className="mt-4 flex gap-3">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1"
                  onClick={() => setConfirmingClose(false)}
                  disabled={isLoading}
                >
                  Keep trade open
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  className="flex-1"
                  onClick={onClosePosition}
                  disabled={isLoading}
                >
                  {isLoading ? "Closing…" : "Close trade"}
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingClose(true)}
              disabled={isLoading}
              className="text-xs font-medium text-danger hover:text-danger/80 disabled:opacity-50"
            >
              Close this trade
            </button>
          )}
        </div>
      )}
    </form>
  );
}

export function ModifyDialog({
  position,
  isOpen,
  onClose,
  onSubmit,
  onClosePosition,
  isLoading,
}: ModifyDialogProps) {
  if (!position) return null;

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title="Review trade">
      {/* Use key to reset form state when position changes */}
      <ModifyForm
        key={position.ticket}
        position={position}
        onClose={onClose}
        onSubmit={onSubmit}
        onClosePosition={onClosePosition}
        isLoading={isLoading}
      />
    </Dialog>
  );
}
