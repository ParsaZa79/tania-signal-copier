"""Orders router for placing and managing orders."""

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_mt5_executor
from ..schemas.order import (
    CancelOrderResponse,
    OrderType,
    PendingOrderResponse,
    PlaceOrderRequest,
    PlaceOrderResponse,
)
from ..symbol_utils import to_broker_symbol
from ..trading.models import OrderType as TradingOrderType
from ..trading.models import TradeSignal

router = APIRouter()

# Map API request types to neutral execution types.
ORDER_TYPE_MAP = {
    OrderType.BUY: TradingOrderType.BUY,
    OrderType.SELL: TradingOrderType.SELL,
    OrderType.BUY_LIMIT: TradingOrderType.BUY_LIMIT,
    OrderType.SELL_LIMIT: TradingOrderType.SELL_LIMIT,
    OrderType.BUY_STOP: TradingOrderType.BUY_STOP,
    OrderType.SELL_STOP: TradingOrderType.SELL_STOP,
}


@router.post("/", response_model=PlaceOrderResponse)
async def place_order(
    request: PlaceOrderRequest,
    executor=Depends(get_mt5_executor),
) -> PlaceOrderResponse:
    """Place a new order.

    Args:
        request: The order request with symbol, type, volume, etc.

    Returns:
        PlaceOrderResponse: The result of placing the order.
    """
    # Convert to TradeSignal for executor
    trading_order_type = ORDER_TYPE_MAP.get(request.order_type)
    if not trading_order_type:
        raise HTTPException(status_code=400, detail=f"Invalid order type: {request.order_type}")

    # For pending orders, price is required
    is_pending = request.order_type in [
        OrderType.BUY_LIMIT,
        OrderType.SELL_LIMIT,
        OrderType.BUY_STOP,
        OrderType.SELL_STOP,
    ]
    if is_pending and request.price is None:
        raise HTTPException(status_code=400, detail="Price is required for pending orders")

    requested_symbol = request.symbol.strip()
    signal = TradeSignal(
        symbol=requested_symbol,
        order_type=trading_order_type,
        entry_price=request.price,
        stop_loss=request.sl,
        take_profits=[request.tp] if request.tp else [],
        lot_size=request.volume,
        comment=request.comment,
    )

    result = executor.execute_signal(
        signal,
        lot_size=request.volume,
        broker_symbol=to_broker_symbol(requested_symbol),
    )
    return PlaceOrderResponse(
        success=result.get("success", False),
        ticket=result.get("ticket"),
        volume=result.get("volume"),
        price=result.get("price"),
        symbol=result.get("symbol"),
        error=result.get("error"),
        retcode=result.get("retcode"),
    )


@router.get("/pending", response_model=list[PendingOrderResponse])
async def list_pending_orders(
    symbol: str | None = None,
    executor=Depends(get_mt5_executor),
) -> list[PendingOrderResponse]:
    """Get all pending orders.

    Args:
        symbol: Optional symbol to filter by.

    Returns:
        list[PendingOrderResponse]: List of pending orders.
    """
    broker_symbol = to_broker_symbol(symbol) if symbol else None
    orders = executor.get_pending_orders(symbol=broker_symbol)
    return [
        PendingOrderResponse(
            ticket=order["ticket"],
            symbol=order["symbol"],
            type=_order_type_to_string(order["type"]),
            volume=order["volume"],
            price_open=order["price_open"],
            sl=order["sl"],
            tp=order["tp"],
            comment=order.get("comment", ""),
        )
        for order in orders
    ]


@router.delete("/{ticket}", response_model=CancelOrderResponse)
async def cancel_order(ticket: int, executor=Depends(get_mt5_executor)) -> CancelOrderResponse:
    """Cancel a pending order.

    Args:
        ticket: The order ticket number.

    Returns:
        CancelOrderResponse: The result of canceling the order.
    """
    result = executor.cancel_pending_order(ticket)
    return CancelOrderResponse(
        success=result.get("success", False),
        ticket=ticket,
        error=result.get("error"),
    )


def _order_type_to_string(order_type: int) -> str:
    """Convert MT5 order type int to string."""
    type_map = {
        0: "buy",
        1: "sell",
        2: "buy_limit",
        3: "sell_limit",
        4: "buy_stop",
        5: "sell_stop",
    }
    return type_map.get(order_type, "unknown")
