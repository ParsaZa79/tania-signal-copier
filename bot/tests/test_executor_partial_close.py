"""Unit tests for MT5Executor.partial_close edge cases."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from tania_signal_copier.executor import MT5Executor


def _build_executor(position_volume: float) -> tuple[MT5Executor, SimpleNamespace]:
    """Create an executor with a mocked MT5 adapter."""
    mt5 = SimpleNamespace(
        TRADE_RETCODE_DONE=10009,
        ORDER_TYPE_BUY=0,
        ORDER_TYPE_SELL=1,
        ORDER_TIME_GTC=0,
        ORDER_FILLING_FOK=0,
        ORDER_FILLING_IOC=1,
        ORDER_FILLING_RETURN=2,
    )
    mt5.ping = MagicMock(return_value=True)
    mt5.symbol_info = MagicMock(
        return_value=SimpleNamespace(
            volume_step=0.01,
            volume_min=0.01,
            filling_mode=1,
        )
    )
    mt5.symbol_info_tick = MagicMock(return_value=SimpleNamespace(bid=2900.0, ask=2900.1))
    mt5.order_send = MagicMock(return_value=SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE, comment="ok"))

    executor = MT5Executor(login=123, password="test", server="test")
    executor.connected = True
    executor._mt5 = mt5
    executor._last_ping_time = time.time()
    executor.get_position = MagicMock(
        return_value={
            "ticket": 12345,
            "symbol": "XAUUSD",
            "type": 0,
            "volume": position_volume,
        }
    )
    return executor, mt5


def test_partial_close_skips_when_it_would_become_full_close() -> None:
    """50% of 0.01 rounds to 0.01; this must be skipped, not fully closed."""
    executor, mt5 = _build_executor(position_volume=0.01)

    result = executor.partial_close(ticket=12345, percentage=50)

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["remaining_volume"] == 0.01
    assert result["closed_volume"] == 0.0
    mt5.order_send.assert_not_called()


def test_partial_close_executes_when_partial_is_possible() -> None:
    """50% of 0.02 -> 0.01 should execute as a real partial close."""
    executor, mt5 = _build_executor(position_volume=0.02)

    result = executor.partial_close(ticket=12345, percentage=50)

    assert result["success"] is True
    assert result["skipped"] is False
    assert result["closed_volume"] == 0.01
    assert result["remaining_volume"] == 0.01
    mt5.order_send.assert_called_once()
