"""Trade history service using SQLite."""

import aiosqlite
from datetime import datetime
from pathlib import Path

from ..schemas.account import TradeHistoryEntry

# Database file path
DB_PATH = Path(__file__).parent.parent.parent / "trade_history.db"

# SQL schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trade_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    order_type TEXT NOT NULL,
    volume REAL NOT NULL,
    price_open REAL NOT NULL,
    price_close REAL NOT NULL,
    sl REAL,
    tp REAL,
    profit REAL NOT NULL,
    swap REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NOT NULL,
    source TEXT DEFAULT 'telegram',
    telegram_msg_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_closed_at ON trade_history(closed_at);
CREATE INDEX IF NOT EXISTS idx_trade_history_ticket ON trade_history(ticket);
"""


async def init_database() -> None:
    """Initialize the database and create tables if needed."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLE_SQL)
        await db.commit()
    print(f"Database initialized at {DB_PATH}")


async def add_trade(
    ticket: int,
    symbol: str,
    order_type: str,
    volume: float,
    price_open: float,
    price_close: float,
    profit: float,
    opened_at: datetime,
    closed_at: datetime,
    sl: float | None = None,
    tp: float | None = None,
    swap: float = 0.0,
    commission: float = 0.0,
    source: str = "telegram",
    telegram_msg_id: int | None = None,
) -> int:
    """Add a trade to history.

    Returns:
        int: The new trade's ID.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO trade_history (
                ticket, symbol, order_type, volume, price_open, price_close,
                sl, tp, profit, swap, commission, opened_at, closed_at,
                source, telegram_msg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket,
                symbol,
                order_type,
                volume,
                price_open,
                price_close,
                sl,
                tp,
                profit,
                swap,
                commission,
                opened_at.isoformat(),
                closed_at.isoformat(),
                source,
                telegram_msg_id,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def get_trade_history(
    page: int = 1,
    page_size: int = 50,
    symbol: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[TradeHistoryEntry], int]:
    """Get trade history with pagination.

    Args:
        page: Page number (1-indexed).
        page_size: Number of trades per page.
        symbol: Optional symbol to filter by.
        from_date: Optional start date filter (inclusive).
        to_date: Optional end date filter (inclusive).

    Returns:
        tuple: List of trades and total count.
    """
    offset = (page - 1) * page_size

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Build WHERE clause dynamically
        conditions = []
        params: list = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if from_date:
            conditions.append("closed_at >= ?")
            params.append(from_date.isoformat())

        if to_date:
            conditions.append("closed_at <= ?")
            params.append(to_date.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get total count
        count_query = f"SELECT COUNT(*) FROM trade_history {where_clause}"
        async with db.execute(count_query, params) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0

        # Get trades
        query = f"""
            SELECT * FROM trade_history
            {where_clause}
            ORDER BY closed_at DESC
            LIMIT ? OFFSET ?
        """
        query_params = [*params, page_size, offset]

        async with db.execute(query, query_params) as cursor:
            rows = await cursor.fetchall()

        trades = [
            TradeHistoryEntry(
                id=row["id"],
                ticket=row["ticket"],
                symbol=row["symbol"],
                order_type=row["order_type"],
                volume=row["volume"],
                price_open=row["price_open"],
                price_close=row["price_close"],
                sl=row["sl"],
                tp=row["tp"],
                profit=row["profit"],
                swap=row["swap"],
                commission=row["commission"],
                opened_at=datetime.fromisoformat(row["opened_at"]),
                closed_at=datetime.fromisoformat(row["closed_at"]),
                source=row["source"],
                telegram_msg_id=row["telegram_msg_id"],
            )
            for row in rows
        ]

        return trades, total


async def get_trade_stats() -> dict:
    """Get trade statistics.

    Returns:
        dict: Trade statistics including total trades, profit, etc.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit,
                MAX(profit) as best_trade,
                MIN(profit) as worst_trade
            FROM trade_history
            """
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_profit": 0,
                "avg_profit": 0,
                "best_trade": 0,
                "worst_trade": 0,
                "win_rate": 0,
            }

        total = row[0] or 0
        winning = row[1] or 0
        return {
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": row[2] or 0,
            "total_profit": row[3] or 0,
            "avg_profit": row[4] or 0,
            "best_trade": row[5] or 0,
            "worst_trade": row[6] or 0,
            "win_rate": (winning / total * 100) if total > 0 else 0,
        }
