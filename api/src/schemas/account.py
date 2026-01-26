"""Account schemas."""

from datetime import datetime

from pydantic import BaseModel


class AccountInfo(BaseModel):
    """Account information."""

    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    leverage: int = 0
    currency: str = "USD"
    name: str = ""


class TradeHistoryEntry(BaseModel):
    """A single trade history entry."""

    id: int
    ticket: int
    symbol: str
    order_type: str
    volume: float
    price_open: float
    price_close: float
    sl: float | None = None
    tp: float | None = None
    profit: float
    swap: float = 0.0
    commission: float = 0.0
    opened_at: datetime
    closed_at: datetime
    source: str = "telegram"  # telegram, dashboard, bot
    telegram_msg_id: int | None = None


class TradeHistoryResponse(BaseModel):
    """Response containing trade history."""

    trades: list[TradeHistoryEntry]
    total: int
    page: int = 1
    page_size: int = 50
