import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface PnlBadgeProps {
  value: number;
  showCurrency?: boolean;
  showIcon?: boolean;
  className?: string;
}

export function PnlBadge({
  value,
  showCurrency = true,
  showIcon = true,
  className,
}: PnlBadgeProps) {
  const isPositive = value >= 0;
  const formatted = showCurrency
    ? formatCurrency(Math.abs(value))
    : Math.abs(value).toFixed(2);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold tabular-nums",
        isPositive
          ? "bg-success/10 text-success border border-success/20"
          : "bg-danger/10 text-danger border border-danger/20",
        className
      )}
    >
      {showIcon &&
        (isPositive ? (
          <ArrowUpRight className="w-3 h-3" />
        ) : (
          <ArrowDownRight className="w-3 h-3" />
        ))}
      {isPositive ? "+" : "-"}
      {formatted}
    </span>
  );
}
