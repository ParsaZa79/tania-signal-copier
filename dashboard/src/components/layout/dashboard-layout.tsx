"use client";

import { Sidebar } from "./sidebar";
import { useWebSocket } from "@/hooks/use-websocket";
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { Position, AccountInfo } from "@/types";
import { Bell, Search, ChevronDown } from "lucide-react";
import { getSymbolPrice } from "@/lib/api";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  prevBid?: number;
}

// Context for sharing WebSocket data across pages
interface DashboardContextType {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardLayout");
  }
  return context;
}

interface DashboardLayoutProps {
  children: ReactNode;
}

// Symbols to show in header - the API will resolve the actual broker name
const HEADER_SYMBOLS = [
  { base: "XAUUSD", label: "XAU/USD" },
  { base: "EURUSD", label: "EUR/USD" },
  { base: "GBPUSD", label: "GBP/USD" },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { positions, account, isConnected, error, reconnect } = useWebSocket();
  const [headerPrices, setHeaderPrices] = useState<Record<string, PriceData>>({});

  const fetchHeaderPrices = useCallback(async () => {
    try {
      const results = await Promise.all(
        HEADER_SYMBOLS.map(async (sym) => {
          try {
            // The API's get_symbol_info handles finding the actual broker symbol
            const price = await getSymbolPrice(sym.base);
            return { base: sym.base, data: price };
          } catch {
            return null;
          }
        })
      );

      setHeaderPrices((prev) => {
        const newPrices: Record<string, PriceData> = {};
        results.forEach((result) => {
          if (result?.data) {
            newPrices[result.base] = {
              ...result.data,
              prevBid: prev[result.base]?.bid,
            };
          }
        });
        return newPrices;
      });
    } catch (error) {
      console.error("Failed to fetch header prices:", error);
    }
  }, []);

  useEffect(() => {
    // Use setTimeout to avoid synchronous setState in effect
    const initialFetch = setTimeout(fetchHeaderPrices, 0);
    const interval = setInterval(fetchHeaderPrices, 2000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, [fetchHeaderPrices]);

  return (
    <DashboardContext.Provider
      value={{ positions, account, isConnected, error, reconnect }}
    >
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />

        <div className="flex-1 flex flex-col min-h-screen">
          {/* Top Header Bar */}
          <header className="h-16 border-b border-border-subtle bg-bg-secondary/30 backdrop-blur-xl sticky top-0 z-40">
            <div className="h-full px-6 flex items-center justify-between">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search Any Things"
                  className="w-72 h-10 pl-10 pr-4 rounded-xl bg-bg-tertiary border border-border-subtle text-sm text-text-primary placeholder:text-text-muted focus:border-accent/30 focus:ring-0 transition-colors"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-bg-elevated border border-border-subtle">
                  <span className="text-[10px] text-text-muted font-mono">⌘K</span>
                </div>
              </div>

              {/* Right side */}
              <div className="flex items-center gap-4">
                {/* Market Status Pills */}
                <div className="hidden lg:flex items-center gap-3">
                  {HEADER_SYMBOLS.map((sym, idx) => {
                    const price = headerPrices[sym.base];
                    const colors: Array<"accent" | "success" | "danger"> = ["accent", "success", "danger"];
                    const color = colors[idx % colors.length];

                    if (!price) {
                      return (
                        <div
                          key={sym.base}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-subtle bg-bg-tertiary animate-pulse"
                        >
                          <span className="text-xs font-semibold text-text-muted">{sym.label}</span>
                          <span className="text-xs text-text-muted">---</span>
                        </div>
                      );
                    }

                    const change = price.prevBid
                      ? ((price.bid - price.prevBid) / price.prevBid) * 100
                      : 0;

                    return (
                      <MarketPill
                        key={sym.base}
                        symbol={sym.label}
                        value={price.bid.toFixed(price.bid > 100 ? 2 : 5)}
                        change={change}
                        color={color}
                      />
                    );
                  })}
                </div>

                {/* Notifications */}
                <button className="relative w-10 h-10 rounded-xl bg-bg-tertiary border border-border-subtle flex items-center justify-center hover:border-accent/30 transition-colors">
                  <Bell className="w-4 h-4 text-text-secondary" />
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-accent rounded-full flex items-center justify-center">
                    <span className="text-[9px] font-bold text-bg-primary">3</span>
                  </span>
                </button>

                {/* User */}
                <button className="flex items-center gap-3 pl-3 pr-2 py-1.5 rounded-xl bg-bg-tertiary border border-border-subtle hover:border-accent/30 transition-colors">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center">
                    <span className="text-xs font-bold text-bg-primary">TA</span>
                  </div>
                  <div className="text-left hidden sm:block">
                    <p className="text-sm font-medium text-text-primary">Tania</p>
                    <p className="text-[10px] text-text-muted">Admin</p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-text-muted" />
                </button>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main className="flex-1 p-6 overflow-auto">
            {/* Connection Error Banner */}
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-danger/10 border border-danger/30 flex items-center justify-between animate-fade-in">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-danger/20 flex items-center justify-center">
                    <span className="text-danger font-bold">!</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-danger">Connection Error</p>
                    <p className="text-xs text-text-muted">{error}</p>
                  </div>
                </div>
                <button
                  onClick={reconnect}
                  className="px-4 py-2 rounded-lg bg-danger/20 text-sm font-medium text-danger hover:bg-danger/30 transition-colors"
                >
                  Reconnect
                </button>
              </div>
            )}
            {children}
          </main>
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

// Market status pill component
function MarketPill({
  symbol,
  value,
  change,
  color,
}: {
  symbol: string;
  value: string;
  change: number;
  color: "success" | "danger" | "accent";
}) {
  const isPositive = change >= 0;

  const colorStyles = {
    success: "border-success/40 bg-success/10",
    danger: "border-danger/40 bg-danger/10",
    accent: "border-accent/40 bg-accent/10",
  };

  const textColor = {
    success: "text-success",
    danger: "text-danger",
    accent: "text-accent",
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${colorStyles[color]}`}>
      <span className={`text-xs font-semibold ${textColor[color]}`}>{symbol}</span>
      <span className="text-xs font-medium text-text-primary tabular-nums">{value}</span>
      <span
        className={`text-[10px] font-bold tabular-nums px-1.5 py-0.5 rounded ${
          isPositive ? "bg-success/25 text-success" : "bg-danger/25 text-danger"
        }`}
      >
        {isPositive ? "↑" : "↓"} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}
