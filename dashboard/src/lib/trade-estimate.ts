export interface TradeEstimateInput {
  entryPrice: number;
  exitPrice: number;
  isBuy: boolean;
  point: number;
  tickValue: number;
  volume: number;
}

/**
 * Estimate gross P&L in the account currency using the broker-reported value
 * of one price point for one lot. Positive values are profit and negative
 * values are loss.
 */
export function estimateTradeOutcome({
  entryPrice,
  exitPrice,
  isBuy,
  point,
  tickValue,
  volume,
}: TradeEstimateInput): number | null {
  if (
    !Number.isFinite(entryPrice) ||
    !Number.isFinite(exitPrice) ||
    !Number.isFinite(point) ||
    !Number.isFinite(tickValue) ||
    !Number.isFinite(volume) ||
    entryPrice <= 0 ||
    exitPrice <= 0 ||
    point <= 0 ||
    tickValue <= 0 ||
    volume <= 0
  ) {
    return null;
  }

  const directionalMove = isBuy
    ? exitPrice - entryPrice
    : entryPrice - exitPrice;

  return (directionalMove / point) * tickValue * volume;
}

export function formatSignedCurrency(
  value: number,
  currency: string = "USD"
): string {
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(value));

  if (value < 0) return `−${formatted}`;
  if (value > 0) return `+${formatted}`;
  return formatted;
}
