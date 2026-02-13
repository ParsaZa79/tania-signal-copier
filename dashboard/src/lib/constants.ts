// API configuration
// Default to production URLs. In standalone builds, NEXT_PUBLIC_* env vars
// are NOT inlined due to Next.js bug (vercel/next.js#80194), so the fallback
// is the production URL. In dev mode, env vars work normally via .env.local.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://api.kiaparsaprintingmoneymachine.cloud";
export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "wss://api.kiaparsaprintingmoneymachine.cloud/ws";

// Available symbols
export const SYMBOLS = [
  { value: "XAUUSD", label: "XAUUSD (Gold)" },
  { value: "EURUSD", label: "EURUSD" },
  { value: "GBPUSD", label: "GBPUSD" },
  { value: "USDJPY", label: "USDJPY" },
  { value: "AUDUSD", label: "AUDUSD" },
  { value: "USDCAD", label: "USDCAD" },
  { value: "XAGUSD", label: "XAGUSD (Silver)" },
];

// Order types
export const ORDER_TYPES = [
  { value: "buy", label: "Buy (Market)" },
  { value: "sell", label: "Sell (Market)" },
  { value: "buy_limit", label: "Buy Limit" },
  { value: "sell_limit", label: "Sell Limit" },
  { value: "buy_stop", label: "Buy Stop" },
  { value: "sell_stop", label: "Sell Stop" },
];

// Pending order types
export const PENDING_ORDER_TYPES = [
  "buy_limit",
  "sell_limit",
  "buy_stop",
  "sell_stop",
];
