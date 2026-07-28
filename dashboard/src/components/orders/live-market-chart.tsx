"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { normalizeSymbol } from "@/lib/symbol-icon-resolver";

interface LiveMarketChartProps {
  symbol: string;
}

const TRADING_VIEW_WIDGET_URL =
  "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

const TRADING_VIEW_SYMBOLS: Record<string, string> = {
  XAUUSD: "OANDA:XAUUSD",
  XAGUSD: "OANDA:XAGUSD",
  BTCUSD: "BITSTAMP:BTCUSD",
  ETHUSD: "COINBASE:ETHUSD",
};

export function toTradingViewSymbol(symbol: string): string {
  const normalized = normalizeSymbol(symbol);

  if (/^(US30|DJ30|DOW)/.test(normalized)) return "OANDA:US30USD";
  if (/^(US500|SP500|SPX)/.test(normalized)) return "OANDA:SPX500USD";
  if (/^(NAS100|USTEC|US100|NDX)/.test(normalized)) {
    return "OANDA:NAS100USD";
  }
  if (/^(DE40|GER40|DAX)/.test(normalized)) return "OANDA:DE30EUR";
  if (/^(UK100|FTSE|UKX)/.test(normalized)) return "OANDA:UK100GBP";

  const base = normalized.slice(0, 6);
  return TRADING_VIEW_SYMBOLS[base] ?? `OANDA:${base}`;
}

export function LiveMarketChart({ symbol }: LiveMarketChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadState, setLoadState] = useState<{
    key: string;
    status: "ready" | "error";
  }>({ key: "", status: "ready" });
  const tradingViewSymbol = useMemo(
    () => toTradingViewSymbol(symbol),
    [symbol]
  );
  const loadKey = `${tradingViewSymbol}:${reloadKey}`;
  const status = loadState.key === loadKey ? loadState.status : "loading";

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !symbol) return;

    let disposed = false;
    container.replaceChildren();

    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    widget.style.width = "100%";
    widget.style.height = "100%";

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.src = TRADING_VIEW_WIDGET_URL;
    script.async = true;
    script.textContent = JSON.stringify({
      autosize: true,
      symbol: tradingViewSymbol,
      interval: "15",
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "#09090b",
      gridColor: "rgba(255, 255, 255, 0.06)",
      allow_symbol_change: false,
      calendar: false,
      details: false,
      hide_legend: false,
      hide_side_toolbar: false,
      hide_top_toolbar: false,
      hide_volume: false,
      hotlist: false,
      save_image: true,
      withdateranges: true,
      compareSymbols: [],
      studies: [],
      watchlist: [],
    });
    script.onerror = () => {
      if (!disposed) setLoadState({ key: loadKey, status: "error" });
    };

    const observer = new MutationObserver(() => {
      if (container.querySelector("iframe")) {
        if (!disposed) setLoadState({ key: loadKey, status: "ready" });
        observer.disconnect();
      }
    });
    observer.observe(container, { childList: true, subtree: true });

    const timeout = window.setTimeout(() => {
      if (!container.querySelector("iframe")) {
        if (!disposed) setLoadState({ key: loadKey, status: "error" });
      }
    }, 12_000);

    const appendTimer = window.setTimeout(() => {
      if (!disposed) container.append(widget, script);
    }, 0);

    return () => {
      disposed = true;
      window.clearTimeout(appendTimer);
      observer.disconnect();
      window.clearTimeout(timeout);
      container.replaceChildren();
    };
  }, [loadKey, symbol, tradingViewSymbol]);

  return (
    <section
      className="relative h-[390px] overflow-hidden rounded-xl border border-border-subtle bg-[#131722]"
      aria-label={`${symbol} TradingView advanced chart`}
    >
      <div className="h-[364px] w-full overflow-hidden">
        <div
          ref={containerRef}
          className="tradingview-widget-container h-full w-full"
        />
      </div>
      <div className="flex h-6 items-center justify-end gap-1 bg-[#131722] px-2 text-[10px] text-[#787b86]">
        <a
          href={`https://www.tradingview.com/symbols/${tradingViewSymbol.replace(":", "-")}/?utm_source=localhost&utm_medium=widget_new&utm_campaign=advanced-chart`}
          target="_blank"
          rel="noopener nofollow"
          className="font-medium text-[#2962ff] hover:underline"
        >
          Chart
        </a>
        <span>by TradingView</span>
      </div>

      {status === "loading" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#131722]">
          <span className="inline-flex items-center gap-2 text-sm text-[#b2b5be]">
            <RefreshCw className="h-4 w-4 animate-spin text-[#2962ff]" />
            Loading TradingView…
          </span>
        </div>
      )}

      {status === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#131722] px-6 text-center">
          <Activity className="h-5 w-5 text-[#787b86]" />
          <p className="text-sm text-[#b2b5be]">
            TradingView could not be loaded. Check your network and try again.
          </p>
          <button
            type="button"
            onClick={() => setReloadKey((current) => current + 1)}
            className="text-xs font-medium text-[#2962ff] hover:text-[#5b8cff]"
          >
            Try again
          </button>
        </div>
      )}
    </section>
  );
}
