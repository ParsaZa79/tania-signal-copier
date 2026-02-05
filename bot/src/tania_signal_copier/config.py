"""
Configuration for the Telegram MT5 Signal Bot.

This module handles loading configuration from environment variables
with sensible defaults.
"""

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


def _env_optional_float(name: str) -> float | None:
    raw = os.getenv(name, "")
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_channel(value: str) -> str | int:
    """Parse a single channel value - return int if numeric, otherwise string."""
    value = value.strip()
    if not value:
        return ""
    # Check if it's a numeric ID (with optional negative sign for -100 prefix)
    try:
        return int(value)
    except ValueError:
        return value


def _parse_channels(value: str) -> list[str | int]:
    """Parse comma-separated channel values into a list."""
    if not value or not value.strip():
        return []
    # Split by comma and parse each channel
    channels = []
    for ch in value.split(","):
        parsed = _parse_channel(ch)
        if parsed:  # Skip empty strings
            channels.append(parsed)
    return channels


@dataclass
class TelegramConfig:
    """Telegram API configuration."""

    api_id: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    # Support multiple channels (comma-separated)
    channels: list[str | int] = field(
        default_factory=lambda: _parse_channels(os.getenv("TELEGRAM_CHANNEL", ""))
    )
    session_name: str = "signal_bot_session"

    @property
    def channel(self) -> str | int:
        """Get first channel for backwards compatibility."""
        return self.channels[0] if self.channels else ""


@dataclass
class MT5Config:
    """MetaTrader 5 connection configuration."""

    login: int = int(os.getenv("MT5_LOGIN", "0"))
    password: str = os.getenv("MT5_PASSWORD", "")
    server: str = os.getenv("MT5_SERVER", "")
    # Docker settings (macOS only - not used on Windows)
    docker_host: str = os.getenv("MT5_DOCKER_HOST", "localhost")
    docker_port: int = int(os.getenv("MT5_DOCKER_PORT", "8001"))
    # Windows-specific settings
    path: str | None = os.getenv("MT5_PATH")  # Path to MT5 terminal (auto-detected if not set)


@dataclass
class TradingConfig:
    """Trading parameters configuration."""

    default_lot_size: float = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
    max_risk_percent: float = float(os.getenv("MAX_RISK_PERCENT", "10.0")) / 100.0
    scalp_lot_size: float | None = _env_optional_float("SCALP_LOT_SIZE")
    runner_lot_size: float | None = _env_optional_float("RUNNER_LOT_SIZE")
    min_confidence: float = 0.7
    # Timeout in seconds for incomplete signals. 0 = disabled (recommended for swing trades)
    incomplete_signal_timeout: int = int(os.getenv("INCOMPLETE_SIGNAL_TIMEOUT_SECONDS", "0"))
    # Strategy: "dual_tp" (default) or "single"
    strategy_type: str = os.getenv("TRADING_STRATEGY", "dual_tp")
    # Edit handling: ignore edits received after this many seconds (default 30 min)
    edit_window_seconds: int = int(os.getenv("EDIT_WINDOW_SECONDS", "1800"))


@dataclass
class SymbolConfig:
    """Symbol filtering and mapping configuration."""

    allowed_symbols: list[str] = field(default_factory=lambda: ["XAUUSD"])
    symbol_map: dict[str, str] = field(default_factory=lambda: {"XAUUSD": "XAUUSD"})

    def is_allowed(self, symbol: str) -> bool:
        """Check if a symbol is in the allowed list."""
        return symbol in self.allowed_symbols

    def get_broker_symbol(self, symbol: str) -> str:
        """Get the broker-specific symbol name."""
        return self.symbol_map.get(symbol, symbol)


@dataclass
class BotConfig:
    """Main bot configuration combining all settings."""

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    mt5: MT5Config = field(default_factory=MT5Config)
    trading: TradingConfig = field(default_factory=TradingConfig)
    symbols: SymbolConfig = field(default_factory=SymbolConfig)
    state_file: str = "bot_state.json"


# Global config instance
config = BotConfig()
