"""
Configuration for the Telegram MT5 Signal Bot.

This module handles loading configuration from environment variables
with sensible defaults.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TelegramConfig:
    """Telegram API configuration."""

    api_id: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    channel: str = os.getenv("TELEGRAM_CHANNEL", "")
    session_name: str = "signal_bot_session"


@dataclass
class MT5Config:
    """MetaTrader 5 connection configuration."""

    login: int = int(os.getenv("MT5_LOGIN", "0"))
    password: str = os.getenv("MT5_PASSWORD", "")
    server: str = os.getenv("MT5_SERVER", "")
    docker_host: str = os.getenv("MT5_DOCKER_HOST", "localhost")
    docker_port: int = int(os.getenv("MT5_DOCKER_PORT", "8001"))


@dataclass
class TradingConfig:
    """Trading parameters configuration."""

    default_lot_size: float = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
    max_risk_percent: float = float(os.getenv("MAX_RISK_PERCENT", "10.0")) / 100.0
    min_confidence: float = 0.7
    incomplete_signal_timeout: int = 120  # 2 minutes


@dataclass
class SymbolConfig:
    """Symbol filtering and mapping configuration."""

    allowed_symbols: list[str] = field(default_factory=lambda: ["XAUUSD"])
    symbol_map: dict[str, str] = field(default_factory=lambda: {"XAUUSD": "XAUUSDb"})

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
