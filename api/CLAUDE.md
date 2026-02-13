# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is the FastAPI backend for the Trading Dashboard, providing REST and WebSocket APIs for managing MT5 trading positions and orders. It connects to MetaTrader 5 via platform-specific adapters (macOS: `siliconmetatrader5`, Linux: `rpyc` to Docker RPyC server, Windows: native `MetaTrader5`) and shares the MT5Executor from the sibling `bot/` project.

## Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run development server
uv run python -m src.main

# Run with uvicorn directly
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Linting
uv run ruff check src/
uv run ruff check --fix src/

# Type checking
uv run pyright src/

# Run tests
uv run pytest

# Run a single test
uv run pytest path/to/test_file.py::test_function_name -v
```

## Architecture

### Module Loading Strategy

The API uses direct module loading (`importlib.util`) to import `MT5Executor` from the sibling `bot/` project without triggering `telethon` imports. This is done in `src/main.py` - the models, mt5_adapter, and executor modules are loaded explicitly before the FastAPI app initializes.

### Key Components

- **src/main.py**: FastAPI app with lifespan handler that manages MT5 connection and WebSocket broadcaster
- **src/dependencies.py**: Dependency injection for the MT5Executor instance (global singleton pattern)
- **src/routers/**: API endpoints organized by domain:
  - `positions.py`: Get/modify/close open positions
  - `orders.py`: Place/cancel orders (converts API OrderType to bot's TradeSignal)
  - `account.py`: Account info and trade history
  - `symbols.py`: Symbol information
- **src/websocket/**: Real-time updates via WebSocket
  - `manager.py`: Connection manager for tracking WebSocket clients
  - `broadcaster.py`: Background task that polls MT5 and broadcasts position/account updates every second
- **src/services/history_service.py**: SQLite-based trade history storage using aiosqlite
- **src/schemas/**: Pydantic models for request/response validation

### Data Flow

1. On startup, MT5Executor connects to the broker and is stored as a global singleton
2. REST endpoints use FastAPI Depends to get the executor
3. WebSocket broadcaster runs as a background task, polling MT5 every second and pushing updates to connected clients

### Database

Uses SQLite (`trade_history.db`) for trade history persistence. Schema is auto-created on startup via `init_database()`.

### Configuration

All config via environment variables (loaded from `.env`):
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`: MT5 credentials
- `MT5_DOCKER_HOST`, `MT5_DOCKER_PORT`: For Docker-based MT5 connection
- `API_HOST`, `API_PORT`, `CORS_ORIGINS`, `DEBUG`: Server settings
- `DATABASE_URL`: SQLite connection string
- `BOT_STATE_FILE`: Path to bot state JSON (shared with bot/)
