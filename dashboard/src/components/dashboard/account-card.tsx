"use client";

import { GlassCard } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { AccountInfo } from "@/types";
import { Wallet, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight } from "lucide-react";

interface AccountCardProps {
  account: AccountInfo | null;
}

export function AccountCard({ account }: AccountCardProps) {
  if (!account) {
    return (
      <GlassCard className="animate-pulse">
        <div className="flex items-start justify-between mb-4">
          <div className="w-11 h-11 rounded-xl bg-bg-tertiary" />
          <div className="w-16 h-5 rounded bg-bg-tertiary" />
        </div>
        <div className="space-y-2">
          <div className="w-20 h-4 rounded bg-bg-tertiary" />
          <div className="w-32 h-8 rounded bg-bg-tertiary" />
        </div>
        <div className="mt-4 pt-4 border-t border-border-subtle">
          <div className="w-full h-4 rounded bg-bg-tertiary" />
        </div>
      </GlassCard>
    );
  }

  const profitPercent =
    account.balance > 0 ? (account.profit / account.balance) * 100 : 0;
  const isPositive = account.profit >= 0;

  return (
    <GlassCard className="group hover:border-accent/30 transition-all duration-300 relative overflow-hidden">
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-accent/10 via-transparent to-transparent" />

      <div className="relative">
        <div className="flex items-start justify-between mb-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent to-accent-dark shadow-lg shadow-accent/20 flex items-center justify-center">
            <Wallet className="w-6 h-6 text-bg-primary" />
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${
            isPositive
              ? "bg-success/10 border-success/30"
              : "bg-danger/10 border-danger/30"
          }`}>
            {isPositive ? (
              <ArrowUpRight className="w-3.5 h-3.5 text-success" />
            ) : (
              <ArrowDownRight className="w-3.5 h-3.5 text-danger" />
            )}
            <span
              className={`text-xs font-semibold tabular-nums ${
                isPositive ? "text-success" : "text-danger"
              }`}
            >
              {isPositive ? "+" : ""}
              {profitPercent.toFixed(2)}%
            </span>
          </div>
        </div>

        <div>
          <p className="text-xs text-text-muted mb-1">Account Balance</p>
          <div className="flex items-baseline gap-2">
            <p className="text-3xl font-bold text-accent tabular-nums tracking-tight">
              {formatCurrency(account.balance)}
            </p>
            <span className="text-sm text-text-muted">USD</span>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-accent/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isPositive ? (
                <TrendingUp className="w-4 h-4 text-success" />
              ) : (
                <TrendingDown className="w-4 h-4 text-danger" />
              )}
              <span
                className={`text-sm font-semibold tabular-nums ${
                  isPositive ? "text-success" : "text-danger"
                }`}
              >
                {isPositive ? "+" : ""}
                {formatCurrency(account.profit)}
              </span>
            </div>
            <span className="text-[10px] text-accent font-medium">Profit/Loss</span>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
