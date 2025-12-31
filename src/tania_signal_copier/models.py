"""
Data models for the Telegram MT5 Signal Bot.

This module contains all data classes and enums used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderType(Enum):
    """Trading order types supported by MT5."""

    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


class MessageType(Enum):
    """Classification of incoming Telegram messages."""

    NEW_SIGNAL_COMPLETE = "new_signal_complete"
    NEW_SIGNAL_INCOMPLETE = "new_signal_incomplete"
    MODIFICATION = "modification"
    RE_ENTRY = "re_entry"
    PROFIT_NOTIFICATION = "profit_notification"
    CLOSE_SIGNAL = "close_signal"
    COMPOUND_ACTION = "compound_action"
    NOT_TRADING = "not_trading"


class PositionStatus(Enum):
    """Status of a tracked position."""

    OPEN = "open"
    CLOSED = "closed"
    PENDING_COMPLETION = "pending_completion"


@dataclass
class TradeSignal:
    """Parsed trade signal from Telegram message.

    This class represents a fully parsed trading signal with all
    extracted information from the Claude parser.
    """

    # Core signal fields
    symbol: str
    order_type: OrderType
    entry_price: float | None
    stop_loss: float | None
    take_profits: list[float] = field(default_factory=list)
    lot_size: float | None = None

    # Metadata
    comment: str = ""
    confidence: float = 0.5

    # Classification
    message_type: MessageType = MessageType.NEW_SIGNAL_COMPLETE
    is_complete: bool = True

    # Modification fields
    move_sl_to_entry: bool = False
    close_position: bool = False
    new_stop_loss: float | None = None
    new_take_profit: float | None = None

    # Re-entry fields
    re_entry_price: float | None = None
    re_entry_price_max: float | None = None

    # Compound action fields
    actions: list[dict] = field(default_factory=list)


@dataclass
class TrackedPosition:
    """Tracks an open position linked to Telegram signals.

    This class maintains the relationship between a Telegram message
    and its corresponding MT5 position for state management.
    """

    telegram_msg_id: int
    mt5_ticket: int
    symbol: str
    order_type: OrderType
    entry_price: float
    stop_loss: float | None
    take_profits: list[float]
    lot_size: float
    opened_at: datetime
    is_complete: bool
    status: PositionStatus

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "telegram_msg_id": self.telegram_msg_id,
            "mt5_ticket": self.mt5_ticket,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profits": self.take_profits,
            "lot_size": self.lot_size,
            "opened_at": self.opened_at.isoformat(),
            "is_complete": self.is_complete,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackedPosition":
        """Deserialize from dictionary."""
        return cls(
            telegram_msg_id=data["telegram_msg_id"],
            mt5_ticket=data["mt5_ticket"],
            symbol=data["symbol"],
            order_type=OrderType(data["order_type"]),
            entry_price=data["entry_price"],
            stop_loss=data.get("stop_loss"),
            take_profits=data.get("take_profits", []),
            lot_size=data["lot_size"],
            opened_at=datetime.fromisoformat(data["opened_at"]),
            is_complete=data["is_complete"],
            status=PositionStatus(data["status"]),
        )
