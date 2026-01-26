"""Positions router for managing open positions."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_mt5_executor
from ..schemas.position import (
    ClosePositionResponse,
    ModifyPositionRequest,
    ModifyPositionResponse,
    PositionResponse,
)

router = APIRouter()


@router.get("/", response_model=list[PositionResponse])
async def list_positions(executor=Depends(get_mt5_executor)) -> list[PositionResponse]:
    """Get all open positions.

    Returns:
        list[PositionResponse]: List of all open positions.
    """
    if not executor._mt5:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    positions = executor._mt5.positions_get()
    if positions is None:
        return []

    return [
        PositionResponse(
            ticket=pos.ticket,
            symbol=pos.symbol,
            type="buy" if pos.type == 0 else "sell",
            volume=pos.volume,
            price_open=pos.price_open,
            price_current=getattr(pos, "price_current", None),
            sl=pos.sl,
            tp=pos.tp,
            profit=pos.profit,
            swap=getattr(pos, "swap", 0.0),
            commission=getattr(pos, "commission", 0.0),
            time=datetime.fromtimestamp(pos.time) if hasattr(pos, "time") and pos.time else None,
        )
        for pos in positions
    ]


@router.get("/{ticket}", response_model=PositionResponse)
async def get_position(ticket: int, executor=Depends(get_mt5_executor)) -> PositionResponse:
    """Get a single position by ticket.

    Args:
        ticket: The position ticket number.

    Returns:
        PositionResponse: The position details.
    """
    pos = executor.get_position(ticket)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {ticket} not found")

    return PositionResponse(
        ticket=pos["ticket"],
        symbol=pos["symbol"],
        type="buy" if pos["type"] == 0 else "sell",
        volume=pos["volume"],
        price_open=pos["price_open"],
        price_current=pos.get("price_current"),
        sl=pos["sl"],
        tp=pos["tp"],
        profit=pos["profit"],
        swap=pos.get("swap", 0.0),
        commission=pos.get("commission", 0.0),
    )


@router.put("/{ticket}", response_model=ModifyPositionResponse)
async def modify_position(
    ticket: int,
    request: ModifyPositionRequest,
    executor=Depends(get_mt5_executor),
) -> ModifyPositionResponse:
    """Modify a position's SL/TP.

    Args:
        ticket: The position ticket number.
        request: The modification request with new SL/TP values.

    Returns:
        ModifyPositionResponse: The result of the modification.
    """
    result = executor.modify_position(ticket, sl=request.sl, tp=request.tp)
    return ModifyPositionResponse(
        success=result.get("success", False),
        ticket=ticket,
        new_sl=result.get("new_sl"),
        new_tp=result.get("new_tp"),
        error=result.get("error"),
    )


@router.delete("/{ticket}", response_model=ClosePositionResponse)
async def close_position(ticket: int, executor=Depends(get_mt5_executor)) -> ClosePositionResponse:
    """Close an open position.

    Args:
        ticket: The position ticket number.

    Returns:
        ClosePositionResponse: The result of closing the position.
    """
    # Get position profit before closing
    pos = executor.get_position(ticket)
    profit = pos["profit"] if pos else None

    result = executor.close_position(ticket)
    return ClosePositionResponse(
        success=result.get("success", False),
        ticket=ticket,
        closed_at=result.get("closed_at"),
        profit=profit,
        error=result.get("error"),
    )
