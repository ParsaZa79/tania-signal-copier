
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram to MetaTrader 5 Signal Bot - Automates forex trading by reading signals from Telegram channels, parsing them with Claude AI, and executing trades on MT5.

## Development Commands

```bash
# Install dependencies
uv sync --dev

# Run the bot
uv run python -m tania_signal_copier.bot

# Run tests (with coverage)
uv run pytest

# Run a single test
uv run pytest tests/test_bot.py::test_function_name -v

# Run integration tests (requires MT5 Docker running)
uv run pytest -m integration

# Skip integration tests
uv run pytest -m "not integration"

# Linting and formatting
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .

# Type checking
uv run pyright

# Install pre-commit hooks
uv run pre-commit install
```

## Architecture

### Core Components (src/tania_signal_copier/)

- **bot.py**: Main coordinator - `TelegramMT5Bot` class that:
  - Connects to Telegram via Telethon and listens for channel messages
  - Routes messages through the parser for AI classification
  - Handles 7 message types: NEW_SIGNAL_COMPLETE, NEW_SIGNAL_INCOMPLETE, MODIFICATION, RE_ENTRY, PROFIT_NOTIFICATION, CLOSE_SIGNAL, COMPOUND_ACTION
  - Manages position timeouts for incomplete signals (2-minute default)
  - Implements automatic reconnection with exponential backoff

- **parser.py**: `SignalParser` uses Claude Agent SDK to classify messages and extract structured trade data (symbol, entry, SL, TPs, direction)

- **executor.py**: `MT5Executor` handles all MT5 trading operations with auto-reconnection decorator (`@with_reconnect`). Key methods: `execute_signal()`, `modify_position()`, `close_position()`

- **mt5_adapter.py**: `MT5Adapter` wraps siliconmetatrader5 library for Docker-based MT5 connection on macOS/Apple Silicon

- **models.py**: Data classes - `TradeSignal`, `TrackedPosition`, and enums (`OrderType`, `MessageType`, `PositionStatus`)

- **state.py**: `BotState` manages persistent JSON state mapping Telegram message IDs to MT5 positions

- **config.py**: Dataclass-based configuration loaded from environment variables

### Data Flow

1. Telegram message received -> `_process_message()`
2. Message parsed by Claude AI -> `SignalParser.parse_signal()`
3. Signal routed by type -> `_route_signal()` to specific handler
4. Trade executed on MT5 -> `MT5Executor.execute_signal()`
5. Position tracked in state -> `BotState.add_position()`

### MT5 Docker Setup (Required for Running)

MT5 runs via Docker using siliconmetatrader5 (x86_64 emulation on Apple Silicon):
```bash
colima start --arch x86_64 --vm-type=qemu --cpu 4 --memory 8
cd silicon-metatrader5/docker && docker compose up
```
Access VNC at http://localhost:6081/vnc.html (password: 123456) for initial MT5 login.

## Testing

- Unit tests: `tests/test_bot.py`
- Integration tests (require MT5 Docker): `tests/integration/`
- Markers: `@pytest.mark.integration`, `@pytest.mark.slow`
- Async test mode: pytest-asyncio with `asyncio_mode = "auto"`

## Key Dependencies

- **telethon**: Telegram client
- **siliconmetatrader5**: MT5 connection via Docker
- **claude-agent-sdk**: AI-powered signal parsing (uses Claude Code subscription auth, no API key needed)
