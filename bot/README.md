# Tania Signal Copier (Bot)

Telegram-to-MT5 signal copier service.

## What It Does

- Listens to one or more Telegram channels.
- Parses trade messages into structured signals.
- Executes trades on MT5.
- Tracks signal/position state and handles follow-up edits.
- Supports CLI and GUI launch modes.

## Requirements

- Python 3.13+
- `uv` package manager
- MT5 access:
	- macOS: MT5 Docker bridge (`siliconmetatrader5`)
	- Windows: native MT5 terminal
- Telegram API credentials from `https://my.telegram.org`

## Setup

```bash
cd bot
cp .env.example .env
uv sync --dev
```

Update `.env` with your own credentials/settings.

## Run

### Headless Bot

```bash
cd bot
./run_bot.sh
```

### GUI

```bash
cd bot
./run_gui.sh
```

Platform-specific scripts are also available:

- macOS/Linux: `run_bot.sh`, `run_gui.sh`
- Windows: `run_bot.bat`, `run_bot.ps1`, `run_gui.bat`, `run_gui.ps1`

## Important Config Keys

- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- `TELEGRAM_CHANNEL` (comma-separated for multiple channels)
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
- `MT5_DOCKER_HOST`, `MT5_DOCKER_PORT` (macOS Docker bridge)
- `DEFAULT_LOT_SIZE`, `MAX_RISK_PERCENT`
- `TRADING_STRATEGY` (`dual_tp` or `single`)
- `SCALP_LOT_SIZE`, `RUNNER_LOT_SIZE`
- `EDIT_WINDOW_SECONDS`
- `LLM_PROVIDER`, `GROQ_MODEL`, `CEREBRAS_MODEL`, `LLM_MAX_TOKENS`

## Development

```bash
cd bot
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Notes

- Bot state is persisted to `bot_state.json`.
- A lock file prevents multiple bot instances from running simultaneously.
- Log/output files are written under `logs/` and related analysis files under `analysis/`.

