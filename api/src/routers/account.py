"""Account router for account info and trade history."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_mt5_executor
from ..schemas.account import AccountInfo, TradeHistoryEntry, TradeHistoryResponse

router = APIRouter()


@router.get("/", response_model=AccountInfo)
async def get_account_info(executor=Depends(get_mt5_executor)) -> AccountInfo:
    """Get account information.

    Returns:
        AccountInfo: Account balance, equity, margin, etc.
    """
    if not executor._mt5:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    account = executor._mt5.account_info()
    if not account:
        raise HTTPException(status_code=503, detail="Could not retrieve account info")

    return AccountInfo(
        balance=account.balance,
        equity=account.equity,
        margin=account.margin,
        free_margin=account.margin_free,
        profit=account.profit,
        leverage=getattr(account, "leverage", 0),
        currency=getattr(account, "currency", "USD"),
        name=getattr(account, "name", ""),
    )


@router.get("/history", response_model=TradeHistoryResponse)
async def get_trade_history(
    page: int = 1,
    page_size: int = 50,
    symbol: str | None = None,
    from_date: str | None = Query(None, description="Start date filter (ISO format)"),
    to_date: str | None = Query(None, description="End date filter (ISO format)"),
    days: int = 90,
    executor=Depends(get_mt5_executor),
) -> TradeHistoryResponse:
    """Get trade history from MT5.

    Args:
        page: Page number (1-indexed).
        page_size: Number of trades per page.
        symbol: Optional symbol to filter by.
        from_date: Optional start date filter (ISO format, e.g., 2024-01-01).
        to_date: Optional end date filter (ISO format, e.g., 2024-12-31).
        days: Number of days to look back (default 90, used if no date range).

    Returns:
        TradeHistoryResponse: List of historical trades.
    """
    # Parse date strings to datetime objects
    parsed_from_date: datetime | None = None
    parsed_to_date: datetime | None = None

    if from_date:
        try:
            dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            # If no timezone, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_from_date = dt
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid from_date format: {from_date}. Use ISO format (e.g., 2024-01-01)",
            )

    if to_date:
        try:
            dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            # If no timezone, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # If only date provided (time is 00:00:00), extend to end of day
            if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                dt = dt + timedelta(days=1) - timedelta(seconds=1)
            parsed_to_date = dt
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid to_date format: {to_date}. Use ISO format (e.g., 2024-12-31)",
            )

    # Get deals from MT5 with date filtering
    # Always extend to_date to now() to include most recent trades
    effective_to_date = parsed_to_date
    if effective_to_date is None or effective_to_date < datetime.now(timezone.utc):
        # If no to_date or it's in the past relative to now, use now to catch recent trades
        now = datetime.now(timezone.utc)
        if effective_to_date is None or now.date() <= effective_to_date.date():
            effective_to_date = now

    deals = executor.get_history_deals(
        date_from=parsed_from_date,
        date_to=effective_to_date,
        days=days,
    )

    # Filter by symbol if specified
    if symbol:
        deals = [d for d in deals if d["symbol"] == symbol]

    # Sort by time descending (newest first)
    deals.sort(key=lambda x: x["time"], reverse=True)

    # Pagination
    total = len(deals)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_deals = deals[start:end]

    # Convert to response format
    trades = [
        TradeHistoryEntry(
            id=i + start + 1,
            ticket=deal["ticket"],
            symbol=deal["symbol"],
            order_type="buy" if deal["type"] == 0 else "sell",
            volume=round(deal["volume"], 2),  # Round to 2 decimals for lot size precision
            price_open=0.0,  # Not available in deal, would need order history
            price_close=deal["price"],
            sl=None,
            tp=None,
            profit=round(deal["profit"], 2),
            swap=round(deal["swap"], 2),
            commission=round(deal["commission"], 2),
            opened_at=deal["time"],  # Using close time as placeholder
            closed_at=deal["time"],
            source="mt5",
            telegram_msg_id=None,
        )
        for i, deal in enumerate(paginated_deals)
    ]

    return TradeHistoryResponse(
        trades=trades,
        total=total,
        page=page,
        page_size=page_size,
    )
