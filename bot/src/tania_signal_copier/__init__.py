"""
Tania Signal Copier - Telegram to MetaTrader 5 Signal Bot

This package provides a bot that monitors Telegram channels for trading signals
and automatically executes trades on MetaTrader 5.

Main Components:
    - TelegramMT5Bot: Main bot coordinator
    - SignalParser: Claude-powered signal classifier
    - MT5Executor: MetaTrader 5 trade executor
    - BotState: Persistent state manager

Example:
    >>> from tania_signal_copier import TelegramMT5Bot
    >>> import asyncio
    >>> bot = TelegramMT5Bot()
    >>> asyncio.run(bot.start())
"""

from tania_signal_copier.bot import TelegramMT5Bot
from tania_signal_copier.config import BotConfig, config
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import (
    MessageType,
    OrderType,
    PositionStatus,
    TrackedPosition,
    TradeSignal,
)
from tania_signal_copier.parser import SignalParser
from tania_signal_copier.state import BotState

__all__ = [
    # Main bot
    "TelegramMT5Bot",
    # Components
    "SignalParser",
    "MT5Executor",
    "BotState",
    # Configuration
    "BotConfig",
    "config",
    # Models
    "OrderType",
    "MessageType",
    "PositionStatus",
    "TradeSignal",
    "TrackedPosition",
]

__version__ = "0.1.0"
