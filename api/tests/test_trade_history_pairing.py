"""Tests for reconstructing MT5 closed trades from entry and exit deals."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.routers.account import get_trade_history
from src.trading.executor import MT5Executor, _pair_closed_deals


def _deal(
    *,
    ticket: int,
    position_id: int,
    entry: int,
    deal_type: int,
    volume: float,
    price: float,
    time: int,
    profit: float = 0.0,
):
    return SimpleNamespace(
        ticket=ticket,
        order=ticket + 1000,
        position_id=position_id,
        entry=entry,
        type=deal_type,
        volume=volume,
        price=price,
        time=time,
        time_msc=time * 1000,
        symbol="XAUUSDb",
        profit=profit,
        swap=0.0,
        commission=0.0,
        comment="",
    )


def test_pairs_exit_with_entry_price_direction_and_time() -> None:
    entry = _deal(
        ticket=1,
        position_id=77,
        entry=0,
        deal_type=0,
        volume=0.02,
        price=5010.25,
        time=1_700_000_000,
    )
    exit_deal = _deal(
        ticket=2,
        position_id=77,
        entry=1,
        deal_type=1,
        volume=0.02,
        price=5035.75,
        time=1_700_000_600,
        profit=50.0,
    )

    result = _pair_closed_deals([exit_deal, entry])

    assert len(result) == 1
    assert result[0]["price_open"] == pytest.approx(5010.25)
    assert result[0]["price"] == pytest.approx(5035.75)
    assert result[0]["type"] == 0
    assert result[0]["opened_at"].timestamp() == 1_700_000_000
    assert result[0]["time"].timestamp() == 1_700_000_600


def test_uses_volume_weighted_open_for_multiple_fills_and_partial_closes() -> None:
    deals = [
        _deal(
            ticket=1,
            position_id=88,
            entry=0,
            deal_type=1,
            volume=0.01,
            price=5100,
            time=1_700_000_000,
        ),
        _deal(
            ticket=2,
            position_id=88,
            entry=0,
            deal_type=1,
            volume=0.02,
            price=5130,
            time=1_700_000_100,
        ),
        _deal(
            ticket=3,
            position_id=88,
            entry=1,
            deal_type=0,
            volume=0.01,
            price=5090,
            time=1_700_000_200,
        ),
        _deal(
            ticket=4,
            position_id=88,
            entry=1,
            deal_type=0,
            volume=0.02,
            price=5080,
            time=1_700_000_300,
        ),
    ]

    result = _pair_closed_deals(deals)

    assert len(result) == 2
    assert result[0]["price_open"] == pytest.approx(5120)
    assert result[1]["price_open"] == pytest.approx(5120)
    assert all(trade["type"] == 1 for trade in result)


class HistoryExecutor:
    def get_history_deals(self, **_kwargs):
        return [
            {
                "ticket": 44,
                "position_id": 33,
                "symbol": "XAUUSDb",
                "type": 0,
                "volume": 0.02,
                "price_open": 5010.25,
                "price": 5035.75,
                "profit": 50.0,
                "swap": 0.0,
                "commission": 0.0,
                "opened_at": datetime(2026, 3, 4, 12, tzinfo=UTC),
                "time": datetime(2026, 3, 4, 14, tzinfo=UTC),
            }
        ]


def test_history_response_uses_reconstructed_opening_values() -> None:
    response = asyncio.run(
        get_trade_history(
            page=1,
            page_size=20,
            symbol=None,
            from_date=None,
            to_date=None,
            days=90,
            executor=HistoryExecutor(),
        )
    )

    assert response.total == 1
    assert response.trades[0].price_open == pytest.approx(5010.25)
    assert response.trades[0].opened_at == datetime(2026, 3, 4, 12, tzinfo=UTC)
    assert response.trades[0].order_type == "buy"


def test_fetches_entry_outside_window_without_returning_old_exits() -> None:
    entry = _deal(
        ticket=1,
        position_id=99,
        entry=0,
        deal_type=0,
        volume=0.02,
        price=5000,
        time=1_700_000_000,
    )
    old_partial_exit = _deal(
        ticket=2,
        position_id=99,
        entry=1,
        deal_type=1,
        volume=0.01,
        price=5010,
        time=1_700_000_100,
    )
    requested_exit = _deal(
        ticket=3,
        position_id=99,
        entry=1,
        deal_type=1,
        volume=0.01,
        price=5020,
        time=1_700_000_200,
    )

    class HistoryAdapter:
        def history_deals_get(self, *_args, position=None):
            if position == 99:
                return [entry, old_partial_exit, requested_exit]
            return [requested_exit]

    executor = object.__new__(MT5Executor)
    executor._mt5 = HistoryAdapter()

    result = MT5Executor.get_history_deals.__wrapped__(
        executor,
        date_from=datetime(2026, 1, 1, tzinfo=UTC),
        date_to=datetime(2026, 12, 31, tzinfo=UTC),
    )

    assert [trade["ticket"] for trade in result] == [3]
    assert result[0]["price_open"] == pytest.approx(5000)
    assert result[0]["opened_at"].timestamp() == 1_700_000_000
