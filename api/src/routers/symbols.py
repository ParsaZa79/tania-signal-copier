"""Symbols router for symbol information and prices."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_mt5_executor

router = APIRouter()


class SymbolInfo(BaseModel):
    """Symbol information."""

    symbol: str
    digits: int
    point: float
    volume_min: float
    volume_max: float
    volume_step: float
    trade_tick_value: float
    visible: bool


class SymbolListItem(BaseModel):
    """Symbol list item with value and label."""

    value: str
    label: str


class PriceResponse(BaseModel):
    """Current price response."""

    symbol: str
    bid: float
    ask: float
    spread: float


# Priority symbols to show at the top (common forex and commodity symbols)
PRIORITY_SYMBOLS = [
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "NZDUSD",
    "XAGUSD",
]


def _get_symbol_label(symbol: str) -> str:
    """Get a display label for a symbol."""
    # Remove common broker suffixes for display
    base = symbol.rstrip("b").rstrip(".")
    if base == "XAUUSD":
        return f"{symbol} (Gold)"
    elif base == "XAGUSD":
        return f"{symbol} (Silver)"
    return symbol


@router.get("/", response_model=list[SymbolListItem])
async def list_symbols(executor=Depends(get_mt5_executor)) -> list[SymbolListItem]:
    """Get list of available symbols from the broker.

    Returns:
        list[SymbolListItem]: List of symbol names with labels.
    """
    if not executor._mt5:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    # Get all symbols from MT5
    all_symbols = executor._mt5.symbols_get()
    if not all_symbols:
        raise HTTPException(status_code=503, detail="Could not fetch symbols from MT5")

    # Filter to visible/tradeable symbols
    symbol_names = []
    for sym in all_symbols:
        # Only include visible symbols that can be traded
        if hasattr(sym, "visible") and sym.visible and hasattr(sym, "name"):
            symbol_names.append(sym.name)

    # Sort: priority symbols first, then alphabetically
    def sort_key(name: str) -> tuple[int, int, str]:
        # Check if this symbol matches any priority symbol (with or without suffix)
        base_name = name.rstrip("b").rstrip(".")
        try:
            priority_idx = PRIORITY_SYMBOLS.index(base_name)
            return (0, priority_idx, name)
        except ValueError:
            return (1, 0, name)

    symbol_names.sort(key=sort_key)

    return [SymbolListItem(value=name, label=_get_symbol_label(name)) for name in symbol_names]


@router.get("/{symbol}/info", response_model=SymbolInfo)
async def get_symbol_info(symbol: str, executor=Depends(get_mt5_executor)) -> SymbolInfo:
    """Get detailed information about a symbol.

    Args:
        symbol: The symbol name.

    Returns:
        SymbolInfo: Symbol details including digits, lot sizes, etc.
    """
    info = executor.get_symbol_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    symbol_info = info["info"]
    return SymbolInfo(
        symbol=info["symbol"],
        digits=symbol_info.digits,
        point=symbol_info.point,
        volume_min=symbol_info.volume_min,
        volume_max=symbol_info.volume_max,
        volume_step=getattr(symbol_info, "volume_step", 0.01),
        trade_tick_value=symbol_info.trade_tick_value,
        visible=symbol_info.visible,
    )


@router.get("/{symbol}/price", response_model=PriceResponse)
async def get_symbol_price(symbol: str, executor=Depends(get_mt5_executor)) -> PriceResponse:
    """Get current bid/ask price for a symbol.

    Args:
        symbol: The symbol name.

    Returns:
        PriceResponse: Current bid and ask prices.
    """
    if not executor._mt5:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    # Try to get the symbol with variations
    info = executor.get_symbol_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    actual_symbol = info["symbol"]
    tick = executor._mt5.symbol_info_tick(actual_symbol)
    if not tick:
        raise HTTPException(status_code=503, detail=f"Could not get price for {symbol}")

    spread = round((tick.ask - tick.bid) / info["info"].point, 1)
    return PriceResponse(
        symbol=actual_symbol,
        bid=tick.bid,
        ask=tick.ask,
        spread=spread,
    )
