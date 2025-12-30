"""
Integration test fixtures for MT5 testing.

Provides fixtures for MT5Adapter and MT5Executor with automatic
skip when Docker container is unavailable.
"""

import os
from typing import Generator

import pytest

from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import OrderType, TradeSignal
from tania_signal_copier.mt5_adapter import MT5Adapter


def is_mt5_available(host: str = "localhost", port: int = 8001) -> bool:
    """Check if MT5 Docker container is available.

    Attempts a quick ping to verify the container is running.
    Does not call shutdown to avoid disrupting connection state.
    """
    try:
        from siliconmetatrader5 import MetaTrader5 as SiliconMT5

        client = SiliconMT5(host=host, port=port, keepalive=False)
        return client.ping()
    except Exception:
        return False


@pytest.fixture(scope="module")
def mt5_available(mt5_credentials: dict | None) -> bool:
    """Check if MT5 is available, skip all tests in module if not."""
    if mt5_credentials is None:
        pytest.skip("MT5 credentials not configured in environment")
        return False

    host = mt5_credentials["host"]
    port = mt5_credentials["port"]

    if not is_mt5_available(host, port):
        pytest.skip(
            f"MT5 Docker container not available at {host}:{port}. "
            "Start container with: colima start --arch x86_64 --vm-type=qemu && docker start mt5"
        )
        return False

    return True


@pytest.fixture(scope="function")
def mt5_adapter(
    mt5_credentials: dict, mt5_available: bool
) -> Generator[MT5Adapter, None, None]:
    """Provide a connected MT5Adapter instance.

    Automatically initializes before test and shuts down after.
    """
    adapter = MT5Adapter(
        host=mt5_credentials["host"],
        port=mt5_credentials["port"],
    )

    assert adapter.initialize(), "Failed to initialize MT5Adapter"

    yield adapter

    adapter.shutdown()


@pytest.fixture(scope="function")
def mt5_executor(
    mt5_credentials: dict, mt5_available: bool
) -> Generator[MT5Executor, None, None]:
    """Provide a connected MT5Executor instance.

    Automatically connects before test and disconnects after.
    """
    executor = MT5Executor(
        login=mt5_credentials["login"],
        password=mt5_credentials["password"],
        server=mt5_credentials["server"],
    )

    assert executor.connect(), "Failed to connect MT5Executor"

    yield executor

    executor.disconnect()


@pytest.fixture
def test_symbol() -> str:
    """Provide a reliable test symbol.

    EURUSD is typically available on all brokers.
    Override via TEST_SYMBOL env var if needed.
    """
    return os.getenv("TEST_SYMBOL", "EURUSD")


@pytest.fixture
def gold_symbol() -> str:
    """Provide gold symbol for testing.

    Note: Gold symbol varies by broker (XAUUSD, XAUUSDb, GOLD, etc.)
    """
    return os.getenv("TEST_GOLD_SYMBOL", "XAUUSD")


@pytest.fixture
def sample_buy_signal(test_symbol: str) -> TradeSignal:
    """Create a sample BUY signal for testing."""
    return TradeSignal(
        symbol=test_symbol,
        order_type=OrderType.BUY,
        entry_price=None,  # Market order
        stop_loss=None,
        take_profits=[],
        lot_size=0.01,
        comment="Integration test BUY",
        confidence=0.95,
    )


@pytest.fixture
def sample_sell_signal(test_symbol: str) -> TradeSignal:
    """Create a sample SELL signal for testing."""
    return TradeSignal(
        symbol=test_symbol,
        order_type=OrderType.SELL,
        entry_price=None,
        stop_loss=None,
        take_profits=[],
        lot_size=0.01,
        comment="Integration test SELL",
        confidence=0.95,
    )
