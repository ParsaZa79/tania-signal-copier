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
  { value: "XAUUSDb", label: "XAUUSDb (Gold)" },
  { value: "EURUSDb", label: "EURUSDb" },
  { value: "GBPUSDb", label: "GBPUSDb" },
  { value: "USDJPYb", label: "USDJPYb" },
  { value: "AUDUSDb", label: "AUDUSDb" },
  { value: "USDCADb", label: "USDCADb" },
  { value: "XAGUSDb", label: "XAGUSDb (Silver)" },
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
