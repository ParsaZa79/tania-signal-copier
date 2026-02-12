# Trading Dashboard API

FastAPI backend for MT5 account/position/order operations, bot lifecycle control, trade history, and real-time dashboard updates.

## Requirements

- Python 3.12+
- `uv` package manager
- Reachable MT5 bridge/terminal credentials

## Setup

```bash
cd api
cp .env.example .env
uv sync
```

## Run

```bash
cd api
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API docs will be available at `http://localhost:8000/docs`.

## Environment Variables

From `src/config.py` / `.env.example`:

- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
- `MT5_DOCKER_HOST`, `MT5_DOCKER_PORT`
- `API_HOST`, `API_PORT`
- `CORS_ORIGINS` (comma-separated)
- `DEBUG`
- `DATABASE_URL`
- `BOT_STATE_FILE`

## Main Endpoints

- Health: `/api/health`
- Positions: `/api/positions`
- Orders: `/api/orders`
- Account & history: `/api/account`
- Symbols: `/api/symbols`
- Telegram tools: `/api/telegram`
- Bot control/status: `/api/bot`
- Runtime config/presets: `/api/config`
- Analysis: `/api/analysis`

## WebSockets

- `ws://localhost:8000/ws` — account/position updates
- `ws://localhost:8000/ws/logs` — live bot log stream

## Development

```bash
cd api
uv run ruff check .
uv run pytest
```