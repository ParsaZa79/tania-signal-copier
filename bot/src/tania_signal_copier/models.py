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
    PARTIAL_CLOSE = "partial_close"
    COMPOUND_ACTION = "compound_action"
    NOT_TRADING = "not_trading"


class PositionStatus(Enum):
    """Status of a tracked position."""

    OPEN = "open"
    CLOSED = "closed"
    PENDING_COMPLETION = "pending_completion"


class TradeRole(Enum):
    """Role of a trade in the dual-trade system."""

    SCALP = "scalp"  # Trade 1 - targets TP1
    RUNNER = "runner"  # Trade 2 - targets last TP
    SINGLE = "single"  # Legacy single trade (re-entry)


class TradeActionType(Enum):
    """Actions that a strategy can request."""

    CLOSE = "close"
    MOVE_SL_TO_BREAKEVEN = "move_sl_to_breakeven"
    MODIFY_SL = "modify_sl"
    MODIFY_TP = "modify_tp"
    VERIFY_CLOSED = "verify_closed"


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
    tp_hit_number: int | None = None  # Which TP was hit (1, 2, 3, etc.)
    close_position: bool = False
    close_percentage: int | None = None  # For partial close (e.g., 70 for "Close 70%")
    new_stop_loss: float | None = None
    new_take_profit: float | None = None

    # Re-entry fields
    re_entry_price: float | None = None
    re_entry_price_max: float | None = None

    # Compound action fields
    actions: list[dict] = field(default_factory=list)


@dataclass
class TradeConfig:
    """Configuration for a trade to be opened by the strategy."""

    role: TradeRole
    tp: float | None
    sl: float | None = None
    lot_multiplier: float = 1.0


@dataclass
class TradeAction:
    """An action requested by the strategy for a specific trade role."""

    action_type: TradeActionType
    role: TradeRole
    value: float | None = None  # e.g., new SL price for MODIFY_SL


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
    tps_hit: list[int] = field(default_factory=list)  # TP numbers already hit
    role: TradeRole = TradeRole.SINGLE  # Default for backward compat

    # Original signal data for edit detection
    original_message_text: str = ""
    original_stop_loss: float | None = None
    original_take_profits: list[float] = field(default_factory=list)

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
            "tps_hit": self.tps_hit,
            "role": self.role.value,
            # Original signal data for edit detection
            "original_message_text": self.original_message_text,
            "original_stop_loss": self.original_stop_loss,
            "original_take_profits": self.original_take_profits,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackedPosition":
        """Deserialize from dictionary."""
        # Handle role with backward compatibility
        role_str = data.get("role", "single")
        try:
            role = TradeRole(role_str)
        except ValueError:
            role = TradeRole.SINGLE

        # Get current values for fallback (backward compat for v2 state)
        stop_loss = data.get("stop_loss")
        take_profits = data.get("take_profits", [])

        return cls(
            telegram_msg_id=data["telegram_msg_id"],
            mt5_ticket=data["mt5_ticket"],
            symbol=data["symbol"],
            order_type=OrderType(data["order_type"]),
            entry_price=data["entry_price"],
            stop_loss=stop_loss,
            take_profits=take_profits,
            lot_size=data["lot_size"],
            opened_at=datetime.fromisoformat(data["opened_at"]),
            is_complete=data["is_complete"],
            status=PositionStatus(data["status"]),
            tps_hit=data.get("tps_hit", []),
            role=role,
            # Original signal data - fallback to current values for v2 state
            original_message_text=data.get("original_message_text", ""),
            original_stop_loss=data.get("original_stop_loss", stop_loss),
            original_take_profits=data.get("original_take_profits", take_profits.copy()),
        )


@dataclass
class DualPosition:
    """Container for dual-trade positions linked to a single signal.

    Supports both scalp (TP1) and runner (last TP) trades.
    """

    telegram_msg_id: int
    scalp: TrackedPosition | None = None
    runner: TrackedPosition | None = None

    @property
    def all_positions(self) -> list[TrackedPosition]:
        """Return all non-None positions."""
        return [p for p in [self.scalp, self.runner] if p is not None]

    @property
    def all_tickets(self) -> list[int]:
        """Return all MT5 tickets."""
        return [p.mt5_ticket for p in self.all_positions]

    @property
    def is_closed(self) -> bool:
        """Check if all positions are closed."""
        positions = self.all_positions
        if not positions:
            return True
        return all(p.status == PositionStatus.CLOSED for p in positions)

    def get_by_role(self, role: TradeRole) -> TrackedPosition | None:
        """Get position by role."""
        if role == TradeRole.SCALP:
            return self.scalp
        elif role == TradeRole.RUNNER:
            return self.runner
        return self.scalp  # SINGLE treated as scalp

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "telegram_msg_id": self.telegram_msg_id,
            "scalp": self.scalp.to_dict() if self.scalp else None,
            "runner": self.runner.to_dict() if self.runner else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DualPosition":
        """Deserialize from dictionary."""
        return cls(
            telegram_msg_id=data["telegram_msg_id"],
            scalp=TrackedPosition.from_dict(data["scalp"]) if data.get("scalp") else None,
            runner=TrackedPosition.from_dict(data["runner"]) if data.get("runner") else None,
        )

    @classmethod
    def from_single(cls, pos: TrackedPosition) -> "DualPosition":
        """Create DualPosition from legacy single TrackedPosition."""
        if pos.role == TradeRole.RUNNER:
            return cls(telegram_msg_id=pos.telegram_msg_id, runner=pos)
        else:
            # SCALP or SINGLE treated as scalp
            return cls(telegram_msg_id=pos.telegram_msg_id, scalp=pos)
