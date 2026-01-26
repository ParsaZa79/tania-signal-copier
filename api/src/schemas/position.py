"""Position schemas."""

from datetime import datetime

from pydantic import BaseModel


class PositionBase(BaseModel):
    """Base position data."""

    ticket: int
    symbol: str
    type: str  # "buy" or "sell"
    volume: float
    price_open: float
    sl: float
    tp: float


class PositionResponse(PositionBase):
    """Position response with additional fields."""

    price_current: float | None = None
    profit: float = 0.0
    swap: float = 0.0
    commission: float = 0.0
    time: datetime | None = None


class ModifyPositionRequest(BaseModel):
    """Request to modify a position's SL/TP."""

    sl: float | None = None
    tp: float | None = None


class ModifyPositionResponse(BaseModel):
    """Response after modifying a position."""

    success: bool
    ticket: int
    new_sl: float | None = None
    new_tp: float | None = None
    error: str | None = None


class ClosePositionResponse(BaseModel):
    """Response after closing a position."""

    success: bool
    ticket: int
    closed_at: float | None = None
    profit: float | None = None
    error: str | None = None
