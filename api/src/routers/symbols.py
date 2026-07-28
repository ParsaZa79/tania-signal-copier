"""Symbols router for symbol information and prices."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_mt5_executor
from ..symbol_utils import to_base_symbol

router = APIRouter()
MT5ExecutorDependency = Annotated[Any, Depends(get_mt5_executor)]


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
    daily_open: float | None = None
    daily_high: float | None = None
    daily_low: float | None = None
    daily_change_percent: float | None = None


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

TIMEFRAME_D1 = 16408
def _get_symbol_label(symbol: str) -> str:
    """Get a display label for a symbol."""
    base = to_base_symbol(symbol)
    if base == "XAUUSD":
        return f"{symbol} (Gold)"
    elif base == "XAGUSD":
        return f"{symbol} (Silver)"
    return symbol


def _rate_value(rate, key: str) -> float | None:
    if rate is None:
        return None
    try:
        value = rate[key]
    except (KeyError, TypeError, IndexError, ValueError):
        value = getattr(rate, key, None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _daily_bar(executor, symbol: str) -> dict[str, float | None]:
    try:
        rates = executor._mt5.copy_rates_from_pos(symbol, TIMEFRAME_D1, 0, 1)
    except Exception:
        return {"open": None, "high": None, "low": None}
    if rates is None or len(rates) == 0:
        return {"open": None, "high": None, "low": None}
    return {
        "open": _rate_value(rates[0], "open"),
        "high": _rate_value(rates[0], "high"),
        "low": _rate_value(rates[0], "low"),
    }


@router.get("/", response_model=list[SymbolListItem])
async def list_symbols(executor: MT5ExecutorDependency) -> list[SymbolListItem]:
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
        base_name = to_base_symbol(name)
        try:
            priority_idx = PRIORITY_SYMBOLS.index(base_name)
            return (0, priority_idx, name)
        except ValueError:
            return (1, 0, name)

    symbol_names.sort(key=sort_key)

    return [SymbolListItem(value=name, label=_get_symbol_label(name)) for name in symbol_names]


@router.get("/{symbol}/info", response_model=SymbolInfo)
async def get_symbol_info(symbol: str, executor: MT5ExecutorDependency) -> SymbolInfo:
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
async def get_symbol_price(symbol: str, executor: MT5ExecutorDependency) -> PriceResponse:
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
    # Ensure symbol is in Market Watch (required for tick data)
    if not info["info"].visible:
        executor._mt5.symbol_select(actual_symbol, True)
    tick = executor._mt5.symbol_info_tick(actual_symbol)
    if not tick:
        raise HTTPException(status_code=503, detail=f"Could not get price for {symbol}")

    spread = round((tick.ask - tick.bid) / info["info"].point, 1)
    daily_bar = _daily_bar(executor, actual_symbol)
    daily_open = daily_bar["open"]
    daily_change_percent = (
        ((tick.bid - daily_open) / daily_open) * 100
        if daily_open and daily_open > 0
        else None
    )
    return PriceResponse(
        symbol=actual_symbol,
        bid=tick.bid,
        ask=tick.ask,
        spread=spread,
        daily_open=daily_open,
        daily_high=daily_bar["high"],
        daily_low=daily_bar["low"],
        daily_change_percent=daily_change_percent,
    )
