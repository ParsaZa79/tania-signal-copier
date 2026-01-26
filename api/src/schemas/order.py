"""Order schemas."""

from enum import Enum

from pydantic import BaseModel


class OrderType(str, Enum):
    """Order types."""

    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


class PlaceOrderRequest(BaseModel):
    """Request to place a new order."""

    symbol: str
    order_type: OrderType
    volume: float
    price: float | None = None  # Required for pending orders
    sl: float | None = None
    tp: float | None = None
    comment: str = "Dashboard Order"


class PlaceOrderResponse(BaseModel):
    """Response after placing an order."""

    success: bool
    ticket: int | None = None
    volume: float | None = None
    price: float | None = None
    symbol: str | None = None
    error: str | None = None
    retcode: int | None = None


class PendingOrderResponse(BaseModel):
    """Pending order details."""

    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    sl: float
    tp: float
    comment: str = ""


class CancelOrderResponse(BaseModel):
    """Response after canceling an order."""

    success: bool
    ticket: int
    error: str | None = None
