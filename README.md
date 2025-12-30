# Tania Signal Copier

Telegram to MetaTrader 5 Signal Bot - Automates forex trading by reading signals from Telegram and executing on MT5.

## Features

- Monitors Telegram channels for trading signals
- Uses Claude AI to parse various signal formats
- Executes trades on MetaTrader 5 via Docker (Apple Silicon)

## Requirements

- macOS (Apple Silicon)
- Python 3.12+
- Docker (via Colima)
- Telegram API credentials (from https://my.telegram.org)
- Anthropic API key (from https://console.anthropic.com)
- MetaTrader 5 account

## MT5 Docker Setup

MT5 runs via Docker using [siliconmetatrader5](https://github.com/bahadirumutiscimen/silicon-metatrader5):

```bash
# Install dependencies
brew install colima docker qemu lima lima-additional-guestagents

# Start Colima with x86_64 emulation (first time takes ~25-30 min)
colima start --arch x86_64 --vm-type=qemu --cpu 4 --memory 8

# Clone and run the MT5 Docker container
git clone https://github.com/bahadirumutiscimen/silicon-metatrader5.git
cd silicon-metatrader5/docker
docker compose up --build

# First-time setup: Access VNC at http://localhost:6081/vnc.html (password: 123456)
# Login to your MT5 account via: File > Open an Account
```

**Daily startup:**
```bash
colima start  # remembers settings
cd silicon-metatrader5/docker && docker compose up
```

## Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --dev

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

## Usage

```bash
# Ensure MT5 Docker is running first, then:
uv run python -m tania_signal_copier.bot
```

## Development

```bash
# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run tests
uv run pytest

# Install pre-commit hooks
uv run pre-commit install
```

## Project Structure

```
tania-signal-copier/
├── src/tania_signal_copier/
│   ├── __init__.py
│   ├── bot.py              # Main bot logic
│   └── mt5_adapter.py      # MT5 adapter for siliconmetatrader5
├── tests/
│   └── test_bot.py
├── pyproject.toml          # Project configuration
├── .pre-commit-config.yaml # Pre-commit hooks
└── .env.example            # Environment template
```

## License

MIT
