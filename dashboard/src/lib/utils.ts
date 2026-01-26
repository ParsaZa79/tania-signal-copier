import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency
 */
export function formatCurrency(
  value: number,
  currency: string = "USD",
  decimals: number = 2
): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a number with fixed decimals
 */
export function formatNumber(value: number, decimals: number = 2): string {
  return value.toFixed(decimals);
}

/**
 * Format a percentage
 */
export function formatPercent(value: number, decimals: number = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

/**
 * Format a timestamp to a readable date/time
 */
export function formatDateTime(timestamp: number | string | null): string {
  if (!timestamp) return "-";
  const date =
    typeof timestamp === "number"
      ? new Date(timestamp * 1000)
      : new Date(timestamp);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Get profit color class
 */
export function getProfitColor(profit: number): string {
  if (profit > 0) return "text-green-600";
  if (profit < 0) return "text-red-600";
  return "text-gray-600";
}

/**
 * Get profit background color class
 */
export function getProfitBgColor(profit: number): string {
  if (profit > 0) return "bg-green-100 text-green-800";
  if (profit < 0) return "bg-red-100 text-red-800";
  return "bg-gray-100 text-gray-800";
}
