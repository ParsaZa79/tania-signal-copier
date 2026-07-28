"use client";

import { cn } from "@/lib/utils";
import {
  resolveSymbolIcon,
  TRADING_VIEW_LOGO_BASE,
  normalizeSymbol,
} from "@/lib/symbol-icon-resolver";
import FinancialFlagIcon from "financial-flag-icons";
import { DynamicFlag } from "@sankyu/react-circle-flags";
import Image from "next/image";
import {
  BarChart3,
  Bitcoin,
  DollarSign,
  Droplets,
  Euro,
  Gem,
  JapaneseYen,
  PoundSterling,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

type SymbolTone =
  | "metal"
  | "crypto"
  | "forex"
  | "index"
  | "commodity"
  | "default";

interface SymbolMeta {
  icon: LucideIcon;
  tone: SymbolTone;
}

function getFallbackMeta(symbol: string): SymbolMeta {
  const normalized = normalizeSymbol(symbol);

  if (/XAU|GOLD|XAG|SILVER/.test(normalized)) {
    return { icon: Gem, tone: "metal" };
  }
  if (/BTC|ETH|SOL|ADA|DOT|XRP|LTC|BNB|DOGE|USDT|CRYPTO/.test(normalized)) {
    return { icon: Bitcoin, tone: "crypto" };
  }
  if (/OIL|WTI|BRENT|XBR|NGAS/.test(normalized)) {
    return { icon: Droplets, tone: "commodity" };
  }
  if (/NAS|US30|US500|SPX|SP500|DAX|UK100|JP225|NDX|DE40|USTEC/.test(normalized)) {
    return { icon: BarChart3, tone: "index" };
  }
  if (/EUR/.test(normalized)) {
    return { icon: Euro, tone: "forex" };
  }
  if (/GBP/.test(normalized)) {
    return { icon: PoundSterling, tone: "forex" };
  }
  if (/JPY/.test(normalized)) {
    return { icon: JapaneseYen, tone: "forex" };
  }
  if (/AUD|NZD|CAD|USD|CHF|CNH|HKD|SGD|NOK|SEK|MXN|ZAR|TRY/.test(normalized)) {
    return { icon: DollarSign, tone: "forex" };
  }

  return { icon: TrendingUp, tone: "default" };
}

const toneStyles: Record<
  SymbolTone,
  { container: string; icon: string }
> = {
  metal: {
    container: "bg-warning/10 border-warning/20",
    icon: "text-warning",
  },
  crypto: {
    container: "bg-accent/10 border-accent/20",
    icon: "text-accent",
  },
  forex: {
    container: "bg-info/10 border-info/20",
    icon: "text-info",
  },
  index: {
    container: "bg-success/10 border-success/20",
    icon: "text-success",
  },
  commodity: {
    container: "bg-danger/10 border-danger/20",
    icon: "text-danger",
  },
  default: {
    container: "bg-bg-tertiary border-border-subtle",
    icon: "text-text-secondary",
  },
};

const sizeStyles = {
  sm: { box: "w-8 h-8 rounded-lg", icon: "w-3.5 h-3.5", px: 24 },
  md: { box: "w-9 h-9 rounded-lg", icon: "w-4 h-4", px: 32 },
  lg: { box: "w-10 h-10 rounded-xl", icon: "w-[18px] h-[18px]", px: 36 },
};

interface SymbolIconProps {
  symbol: string;
  size?: keyof typeof sizeStyles;
  className?: string;
}

function FallbackSymbolIcon({
  symbol,
  size = "md",
  className,
}: SymbolIconProps) {
  const { icon: Icon, tone } = getFallbackMeta(symbol);
  const styles = toneStyles[tone];
  const dimensions = sizeStyles[size];

  return (
    <div
      className={cn(
        "flex items-center justify-center shrink-0 border",
        dimensions.box,
        styles.container,
        className
      )}
      title={symbol}
    >
      <Icon className={cn(dimensions.icon, styles.icon)} strokeWidth={2} />
    </div>
  );
}

export function SymbolIcon({ symbol, size = "md", className }: SymbolIconProps) {
  const resolved = resolveSymbolIcon(symbol);
  const dimensions = sizeStyles[size];
  const [imageFailed, setImageFailed] = useState(false);

  if (imageFailed || resolved.kind === "fallback") {
    return (
      <FallbackSymbolIcon symbol={symbol} size={size} className={className} />
    );
  }

  const containerClass = cn(
    "flex items-center justify-center shrink-0 overflow-hidden border border-border-subtle bg-bg-secondary",
    dimensions.box,
    className
  );

  if (resolved.kind === "financial-flag" && resolved.key) {
    return (
      <div
        className={cn(
          "flex shrink-0 items-center justify-center overflow-visible",
          dimensions.box,
          className
        )}
        title={symbol}
      >
        <FinancialFlagIcon
          icon={resolved.key}
          className="h-full w-full overflow-visible object-contain"
        />
      </div>
    );
  }

  if (resolved.kind === "tradingview" && resolved.tradingViewPath) {
    return (
      <div className={containerClass} title={symbol}>
        <Image
          src={`${TRADING_VIEW_LOGO_BASE}/${resolved.tradingViewPath}.svg`}
          alt={symbol}
          width={dimensions.px}
          height={dimensions.px}
          unoptimized
          className="h-[70%] w-[70%] object-contain"
          onError={() => setImageFailed(true)}
        />
      </div>
    );
  }

  if (resolved.kind === "circle-flag" && resolved.flagCode) {
    return (
      <div className={containerClass} title={symbol}>
        <DynamicFlag
          code={resolved.flagCode}
          width={dimensions.px}
          height={dimensions.px}
          className="h-full w-full"
        />
      </div>
    );
  }

  return (
    <FallbackSymbolIcon symbol={symbol} size={size} className={className} />
  );
}

interface SymbolCellProps {
  symbol: string;
  label?: string;
  subtitle?: string;
  size?: keyof typeof sizeStyles;
  className?: string;
}

export function SymbolCell({
  symbol,
  label,
  subtitle,
  size = "md",
  className,
}: SymbolCellProps) {
  return (
    <div className={cn("flex items-center gap-3 min-w-0", className)}>
      <SymbolIcon symbol={symbol} size={size} />
      <div className="min-w-0">
        <p className="font-medium text-text-primary text-sm truncate">
          {label ?? symbol}
        </p>
        {subtitle && (
          <p className="text-[10px] text-text-muted truncate">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
