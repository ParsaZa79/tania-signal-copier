"""Regression tests for broker symbol casing at the order boundary."""

import asyncio

import pytest

from src.routers.orders import place_order
from src.schemas.order import OrderType, PlaceOrderRequest
from src.symbol_utils import to_broker_symbol


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("XAUUSD", "XAUUSDb"),
        ("XAUUSDb", "XAUUSDb"),
        ("XAUUSDB", "XAUUSDb"),
        (" xauusdb ", "XAUUSDb"),
    ],
)
def test_to_broker_symbol_preserves_canonical_suffix_case(
    symbol: str,
    expected: str,
) -> None:
    assert to_broker_symbol(symbol) == expected


class CapturingExecutor:
    def __init__(self) -> None:
        self.signal = None
        self.broker_symbol = None

    def execute_signal(self, signal, lot_size=None, broker_symbol=None):
        self.signal = signal
        self.broker_symbol = broker_symbol
        return {
            "success": True,
            "ticket": 123456,
            "volume": lot_size,
            "price": signal.entry_price,
            "symbol": broker_symbol,
        }


def test_place_order_keeps_exact_mt5_symbol_and_uses_canonical_fallback() -> None:
    executor = CapturingExecutor()
    request = PlaceOrderRequest(
        symbol="XAUUSDb",
        order_type=OrderType.SELL_LIMIT,
        volume=0.01,
        price=4069,
        sl=4092,
        tp=4028,
    )

    response = asyncio.run(place_order(request, executor))

    assert response.success is True
    assert executor.signal.symbol == "XAUUSDb"
    assert executor.broker_symbol == "XAUUSDb"
