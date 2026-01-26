# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **dashboard** frontend for a MetaTrader 5 (MT5) trading bot system. It provides a real-time web interface for monitoring trading positions, account status, and trade history. The dashboard connects to a backend API (running on port 8000 by default) via REST and WebSocket.

## Commands

```bash
# Development
bun dev          # Start development server on localhost:3000

# Build
bun run build    # Production build

# Lint
bun run lint     # Run ESLint
```

## Environment Variables

Create `.env.local` with:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

## Architecture

### Tech Stack
- **Next.js 16** with App Router
- **React 19** with TypeScript
- **Tailwind CSS v4** for styling
- **Bun** as package manager/runtime

### Key Architectural Patterns

**WebSocket-based Real-time Updates**: The dashboard maintains a persistent WebSocket connection to receive live position and account updates. This is managed via:
- `src/hooks/use-websocket.ts` - WebSocket connection hook with automatic reconnection
- `src/components/layout/dashboard-layout.tsx` - Context provider that wraps all pages and exposes `useDashboard()` hook

**Page Structure**: All pages are client components ("use client") that consume data from `DashboardContext`:
```tsx
const { positions, account, isConnected, error, reconnect } = useDashboard();
```

**API Layer**: REST API calls are centralized in `src/lib/api.ts`. Endpoints include:
- `/api/health` - Backend health check
- `/api/positions` - CRUD operations on positions
- `/api/orders` - Place/cancel orders
- `/api/account` - Account info and trade history
- `/api/symbols` - Available trading symbols

### Directory Structure

```
src/
├── app/           # Next.js App Router pages
│   ├── page.tsx       # Main dashboard overview
│   ├── positions/     # Positions management
│   ├── orders/        # Order placement
│   ├── history/       # Trade history
│   └── settings/      # Settings page
├── components/
│   ├── dashboard/     # Dashboard-specific components (account card, positions table, etc.)
│   ├── layout/        # Layout components (sidebar, dashboard-layout)
│   ├── ui/            # Reusable UI primitives (button, card, input, dialog, etc.)
│   ├── orders/        # Order-related components
│   └── history/       # History-related components
├── hooks/         # Custom React hooks
├── lib/           # Utilities, constants, API client
└── types/         # TypeScript type definitions
```

### Type Definitions

Core types in `src/types/index.ts`:
- `Position` - Open trading position
- `AccountInfo` - Account balance, equity, margin
- `PlaceOrderRequest` / `PendingOrder` - Order types
- `TradeHistoryEntry` - Closed trade record
- `WebSocketMessage` - Real-time update payload
- `HealthStatus` - Backend health check response

### Path Aliases

The project uses `@/*` as an alias for `./src/*` (configured in tsconfig.json).
