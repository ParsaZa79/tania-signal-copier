// API configuration
// process.env.NODE_ENV is always inlined by Next.js, so the production
// fallback works even if NEXT_PUBLIC_* env vars fail to be injected.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://api.kiaparsaprintingmoneymachine.cloud"
    : "http://localhost:8000");
export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (process.env.NODE_ENV === "production"
    ? "wss://api.kiaparsaprintingmoneymachine.cloud/ws"
    : "ws://localhost:8000/ws");

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
