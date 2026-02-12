# Tania Signal Copier

Multi-service workspace for Telegram signal parsing, MetaTrader 5 execution, and a web dashboard.

## Repository Layout

- `bot/` — Telegram signal copier (Python, `uv`), MT5 execution, GUI, and analysis scripts.
- `api/` — FastAPI backend for dashboard + bot control endpoints and WebSocket streams.
- `dashboard/` — Next.js dashboard UI for account, positions, orders, bot control, and analysis.
- `silicon-metatrader5/` — MT5 Docker setup for Apple Silicon hosts.

## Quick Start (Local)

Run services in this order.

### 1) Start MT5 Docker

```bash
cd silicon-metatrader5/docker
docker compose up --build
```

### 2) Start API

```bash
cd api
cp .env.example .env  # first time only
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### 4) Run Bot (optional, if not started via dashboard)

```bash
cd bot
cp .env.example .env  # first time only
uv sync --dev
./run_bot.sh
```

## Service URLs

- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/health`
- WebSocket: `ws://localhost:8000/ws`

## Environment Files

- `bot/.env` controls Telegram, MT5, strategy, and LLM settings for the copier.
- `api/.env` controls API host/port/CORS and MT5 connection used by backend routes.
- `dashboard/.env.local` can override frontend API endpoints (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`).

## Development Notes

- This repo is a monorepo-like workspace; each app has its own dependencies and lockfile.
- Install/run commands should be executed inside each app directory (`bot`, `api`, `dashboard`).
- `bot/.env.example` and `api/.env.example` should contain non-production placeholders only.

## More Detailed Docs

- Bot setup and workflows: `bot/README.md`
- API setup and endpoints: `api/README.md`
- Dashboard setup and integration: `dashboard/README.md`
