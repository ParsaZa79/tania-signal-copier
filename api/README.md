# Signal Copier API

FastAPI backend for account-scoped MT5 operations and durable copy trading.

## Setup

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Copy-trading storage requires PostgreSQL. Existing SQLite trade history remains available to the legacy account/history endpoints and is stored under `TRADING_DATA_DIR` so container replacements do not discard it.

Public deployment probes:

- `GET /api/health/` — secret-free API and database liveness summary.
- `GET /api/health/ready` — returns HTTP 503 until PostgreSQL is reachable.
- `GET /api/health/mt5` — authenticated account-specific MT5 health details.

## Copy-trading endpoints

- `GET /api/copy/directory` — neutral searchable trader directory with broker-derived statistics.
- `POST/PATCH /api/copy/traders` — opt in or stop sharing a connected account.
- `POST/PATCH /api/copy/subscriptions` — create, pause, resume, or drain a copy relationship.
- `POST /api/copy/subscriptions/{id}/activate-live` — checklist-backed live activation.
- `GET/PUT /api/copy/accounts/{accountId}/risk-policy` — account-wide copying protection.
- `GET /api/copy/overview` and `GET /api/copy/executions` — current status and execution history.
- `POST /api/copy/accounts/{accountId}/emergency-stop` — pause opens or explicitly close all copied positions.
- `POST /api/internal/copy/runtime/heartbeat` and `/events` — authenticated runtime traffic.

Copy subscriptions use an explicit volume mode. `fixed` applies the follower's configured lot
size to every copied entry; `source` uses the trader event's exact lot size. Receiving-broker
minimums, maximums, and increments are validated without silently resizing the order. A separate
dollar daily-loss limit, maximum simultaneous copied trades, and optional stop-loss requirement
can block future entries.

Former Telegram, Bot, Analysis, Prompts, and Platform API paths return `410 Gone` for the deprecation release.

## Runtime contract

Each connected MT5 account has its own managed runtime. Heartbeats include account balance, copy P&L for the day, combined copied-position risk, symbol specifications, and optional verified statistics:

```json
{
  "balance": 10000,
  "daily_copy_pnl": -25,
  "copy_open_risk_pct": 0.5,
  "markets": ["XAUUSD", "EURUSD"],
  "verified_statistics": {
    "return_90d_pct": 8.4,
    "max_drawdown_pct": 4.1,
    "track_record_days": 420,
    "trade_count": 286,
    "pending_orders": [
      {
        "symbol": "XAUUSD",
        "type": "sell_limit",
        "volume": 0.01,
        "price_open": 4069,
        "sl": 4092,
        "tp": 4028
      }
    ]
  },
  "symbol_specs": {
    "XAUUSD": {
      "value_per_price_unit_per_lot": 10,
      "volume_min": 0.01,
      "volume_max": 100,
      "volume_step": 0.01
    }
  }
}
```

The worker blocks missing stops, unavailable symbol specifications, broker volume violations, daily-loss breaches, combined open-risk breaches, and unhealthy runtimes with stable reason codes.

## Environment

- `DATABASE_URL` — PostgreSQL URL for marketplace data and Alembic migrations.
- `PAPER_LIVE_ENABLED=false` — deployment-level live-copying gate.
- `COPY_RUNTIME_INGEST_TOKEN` — bearer token for runtime heartbeats/events.
- `COPY_RUNTIME_MANAGER_URL` and `COPY_RUNTIME_MANAGER_TOKEN` — restricted execution control plane.
- `TRADING_DATA_DIR=/app/data` — persistent compatibility data and the one-time legacy archive source.

Country eligibility and disclosure versions are stored in `app.copy_jurisdiction_policies`. An empty table denies every live activation.

## Verification

```bash
TEST_DATABASE_URL=postgresql+asyncpg://... uv run pytest
uv run ruff check .
uv run pyright
```
