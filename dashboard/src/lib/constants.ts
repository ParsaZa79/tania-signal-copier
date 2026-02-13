// API configuration
// Workaround for Next.js 16 standalone + Turbopack bug (vercel/next.js#80194):
// NEXT_PUBLIC_* env vars are NOT inlined in client components with standalone output.
// Detect environment at runtime via window.location instead of process.env.
function detectUrls(): { api: string; ws: string } {
  if (typeof window !== "undefined") {
    const { hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return {
        api: "http://localhost:8000",
        ws: "ws://localhost:8000/ws",
      };
    }
  }
  return {
    api: "https://api.kiaparsaprintingmoneymachine.cloud",
    ws: "wss://api.kiaparsaprintingmoneymachine.cloud/ws",
  };
}

const _urls = detectUrls();
export const API_URL = _urls.api;
export const WS_URL = _urls.ws;

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
