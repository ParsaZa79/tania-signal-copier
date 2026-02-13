# Tania Signal Copier

Multi-service workspace for Telegram signal parsing, MetaTrader 5 execution, and a web dashboard.

## Repository Layout

- `bot/` — Telegram signal copier (Python, `uv`), MT5 execution, GUI, and analysis scripts.
- `api/` — FastAPI backend for dashboard + bot control endpoints and WebSocket streams.
- `dashboard/` — Next.js dashboard UI for account, positions, orders, bot control, and analysis.
- `silicon-metatrader5/` — MT5 Docker setup for Apple Silicon hosts.

## Quick Start

### Linux (one command)

```bash
./start-linux.sh
```

This starts MT5 Docker, the API, and the dashboard together. See [Linux Setup](#linux-setup) below for prerequisites.

### macOS

Run services in this order:

#### 1) Start MT5 Docker

```bash
cd silicon-metatrader5/docker
docker compose up --build
```

#### 2) Start API

```bash
cd api
cp .env.example .env  # first time only
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3) Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

#### 4) Run Bot (optional, if not started via dashboard)

```bash
cd bot
cp .env.example .env  # first time only
uv sync --dev
./run_bot.sh
```

## Linux Setup

### Prerequisites

- Docker (with compose plugin)
- Python 3.12+ and `uv` package manager
- Node.js 20+ (with npm or bun)

### MT5 Docker Container

Linux uses the [gmag11/metatrader5_vnc](https://github.com/gmag11/MetaTrader5-Docker) Docker image which runs MT5 inside Wine with a VNC web interface and an RPyC server for programmatic access.

```bash
# Option A: Use the start script (recommended)
./start-linux.sh

# Option B: Run manually
docker run -d --name mt5 -p 3000:3000 -p 8001:8001 gmag11/metatrader5_vnc
```

After the container starts:
1. Open `http://localhost:3000` in your browser (VNC web interface)
2. MT5 will auto-install on first run — wait for it to finish
3. Log in to your broker account through the MT5 terminal in VNC

**Important ports:**
- `3000` — VNC web interface (for MT5 GUI access)
- `8001` — RPyC server (how the API/bot connect to MT5 programmatically)

### How MT5 Connection Works on Each Platform

| Platform | Docker Image | Client Library | Connection |
|----------|-------------|---------------|------------|
| **Linux** | `gmag11/metatrader5_vnc` | `rpyc` (direct RPyC classic protocol) | `localhost:8001` |
| **macOS** | `silicon-metatrader5` | `siliconmetatrader5` | `localhost:8001` |
| **Windows** | None (native) | `MetaTrader5` | Direct IPC |

The `mt5_adapter.py` module auto-detects the platform and uses the correct adapter.

## Service URLs

- Dashboard: `http://localhost:3000` (note: shares port with MT5 VNC on Linux — dashboard uses `3001` when started via `start-linux.sh`)
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/health`
- WebSocket: `ws://localhost:8000/ws`
- MT5 VNC (Linux): `http://localhost:3000`

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
