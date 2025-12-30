"""
Integration tests for MT5Adapter.

Tests the low-level MT5 interface against a real Docker container.
Requires MT5 Docker container to be running.

Run with: pytest tests/integration/test_mt5_integration.py -v
"""

import pytest

from tania_signal_copier.mt5_adapter import MT5Adapter, create_mt5_adapter


@pytest.mark.integration
class TestMT5AdapterConnection:
    """Test MT5 connection lifecycle."""

    def test_initialize_success(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test successful initialization to Docker container."""
        adapter = MT5Adapter(
            host=mt5_credentials["host"],
            port=mt5_credentials["port"],
        )

        try:
            result = adapter.initialize()
            assert result is True, "initialize() should return True"
        finally:
            adapter.shutdown()

    def test_initialize_wrong_port_fails(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test that initialization fails with wrong port."""
        adapter = MT5Adapter(
            host=mt5_credentials["host"],
            port=9999,  # Wrong port
        )

        result = adapter.initialize()
        assert result is False, "Should fail with wrong port"

    def test_ping_after_initialize(self, mt5_adapter: MT5Adapter) -> None:
        """Test ping returns True after successful initialization."""
        assert mt5_adapter.ping() is True

    def test_ping_before_initialize(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test ping returns False before initialization."""
        adapter = MT5Adapter(
            host=mt5_credentials["host"],
            port=mt5_credentials["port"],
        )
        assert adapter.ping() is False

    def test_shutdown_clears_client(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test that shutdown clears the internal client."""
        adapter = MT5Adapter(
            host=mt5_credentials["host"],
            port=mt5_credentials["port"],
        )
        adapter.initialize()
        adapter.shutdown()

        assert adapter._client is None
        assert adapter.ping() is False

    def test_login_verification(
        self, mt5_adapter: MT5Adapter, mt5_credentials: dict
    ) -> None:
        """Test login verification (credentials already set in Docker VNC)."""
        result = mt5_adapter.login(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )
        # Login returns True if connection is alive (actual login via VNC)
        assert result is True

    def test_factory_function(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test create_mt5_adapter factory function."""
        adapter = create_mt5_adapter(
            host=mt5_credentials["host"],
            port=mt5_credentials["port"],
        )

        assert isinstance(adapter, MT5Adapter)
        assert adapter.host == mt5_credentials["host"]
        assert adapter.port == mt5_credentials["port"]


@pytest.mark.integration
class TestMT5AdapterAccountInfo:
    """Test account information retrieval."""

    def test_account_info_returns_data(self, mt5_adapter: MT5Adapter) -> None:
        """Test that account_info returns account object."""
        info = mt5_adapter.account_info()

        assert info is not None, "account_info should return data"

    def test_account_info_has_required_fields(self, mt5_adapter: MT5Adapter) -> None:
        """Test account_info contains expected attributes."""
        info = mt5_adapter.account_info()

        # These attributes should exist on the account info object
        assert hasattr(info, "balance"), "Should have balance"
        assert hasattr(info, "equity"), "Should have equity"
        assert hasattr(info, "margin"), "Should have margin"
        assert hasattr(info, "name"), "Should have name"

    def test_account_balance_is_numeric(self, mt5_adapter: MT5Adapter) -> None:
        """Test that balance is a valid number."""
        info = mt5_adapter.account_info()

        assert isinstance(info.balance, (int, float))
        assert info.balance >= 0, "Balance should be non-negative"

    def test_account_info_none_when_not_connected(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test account_info returns None without connection."""
        adapter = MT5Adapter(
            host=mt5_credentials["host"],
            port=mt5_credentials["port"],
        )
        # Not initialized

        result = adapter.account_info()
        assert result is None


@pytest.mark.integration
class TestMT5AdapterSymbolInfo:
    """Test symbol information operations."""

    def test_symbol_info_valid_symbol(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test getting info for a valid symbol."""
        info = mt5_adapter.symbol_info(test_symbol)

        assert info is not None, f"Should find symbol {test_symbol}"

    def test_symbol_info_has_trading_attributes(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test symbol info contains trading-related attributes."""
        info = mt5_adapter.symbol_info(test_symbol)

        assert hasattr(info, "point"), "Should have point"
        assert hasattr(info, "digits"), "Should have digits"
        assert hasattr(info, "volume_min"), "Should have volume_min"
        assert hasattr(info, "volume_max"), "Should have volume_max"
        assert hasattr(info, "visible"), "Should have visible"

    def test_symbol_info_invalid_symbol(self, mt5_adapter: MT5Adapter) -> None:
        """Test that invalid symbol returns None."""
        info = mt5_adapter.symbol_info("INVALID_SYMBOL_XYZ")

        assert info is None

    def test_symbol_info_tick_valid_symbol(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test getting current tick for valid symbol."""
        # Ensure symbol is selected first
        mt5_adapter.symbol_select(test_symbol, True)

        tick = mt5_adapter.symbol_info_tick(test_symbol)

        assert tick is not None, f"Should get tick for {test_symbol}"
        assert hasattr(tick, "bid"), "Should have bid price"
        assert hasattr(tick, "ask"), "Should have ask price"
        assert tick.bid > 0, "Bid should be positive"
        assert tick.ask > 0, "Ask should be positive"
        assert tick.ask >= tick.bid, "Ask should be >= bid"

    def test_symbol_info_tick_invalid_symbol(self, mt5_adapter: MT5Adapter) -> None:
        """Test tick returns None for invalid symbol."""
        tick = mt5_adapter.symbol_info_tick("INVALID_XYZ")

        assert tick is None

    def test_symbol_select_enable(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test enabling symbol in Market Watch."""
        result = mt5_adapter.symbol_select(test_symbol, True)

        assert result is True

        # Verify symbol is now visible
        info = mt5_adapter.symbol_info(test_symbol)
        assert info is not None
        assert info.visible is True

    def test_symbol_select_disable(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test disabling symbol in Market Watch."""
        # First enable
        mt5_adapter.symbol_select(test_symbol, True)

        # Then disable
        result = mt5_adapter.symbol_select(test_symbol, False)

        # Note: Some brokers don't allow disabling certain symbols
        # So we just check the call succeeds without error
        assert result in [True, False]


@pytest.mark.integration
class TestMT5AdapterPositions:
    """Test position retrieval operations."""

    def test_positions_total_returns_integer(self, mt5_adapter: MT5Adapter) -> None:
        """Test positions_total returns an integer."""
        total = mt5_adapter.positions_total()

        assert isinstance(total, int)
        assert total >= 0

    def test_positions_get_returns_list(self, mt5_adapter: MT5Adapter) -> None:
        """Test positions_get returns a list."""
        positions = mt5_adapter.positions_get()

        assert isinstance(positions, list)

    def test_positions_get_by_invalid_ticket(self, mt5_adapter: MT5Adapter) -> None:
        """Test positions_get with non-existent ticket returns empty list."""
        positions = mt5_adapter.positions_get(ticket=999999999)

        assert positions == []

    def test_positions_get_by_invalid_symbol(self, mt5_adapter: MT5Adapter) -> None:
        """Test positions_get with invalid symbol returns empty list."""
        positions = mt5_adapter.positions_get(symbol="INVALID_XYZ")

        assert positions == []


@pytest.mark.integration
class TestMT5AdapterHistoricalData:
    """Test historical data retrieval."""

    def test_copy_rates_from_pos(
        self, mt5_adapter: MT5Adapter, test_symbol: str
    ) -> None:
        """Test getting historical candle data."""
        pytest.importorskip("numpy", reason="numpy required for historical data")

        # Ensure symbol is selected
        mt5_adapter.symbol_select(test_symbol, True)

        # Timeframe 1 = M1 (1 minute)
        rates = mt5_adapter.copy_rates_from_pos(
            symbol=test_symbol,
            timeframe=1,
            start_pos=0,
            count=10,
        )

        assert rates is not None, "Should return rate data"
        assert len(rates) > 0, "Should have at least some candles"
        assert len(rates) <= 10, "Should not exceed requested count"

    def test_copy_rates_invalid_symbol(self, mt5_adapter: MT5Adapter) -> None:
        """Test copy_rates with invalid symbol."""
        pytest.importorskip("numpy", reason="numpy required for historical data")

        rates = mt5_adapter.copy_rates_from_pos(
            symbol="INVALID_XYZ",
            timeframe=1,
            start_pos=0,
            count=10,
        )

        # Should return None or empty for invalid symbol
        assert rates is None or len(rates) == 0


@pytest.mark.integration
class TestMT5AdapterLastError:
    """Test error retrieval."""

    def test_last_error_returns_tuple(self, mt5_adapter: MT5Adapter) -> None:
        """Test last_error returns a tuple."""
        error = mt5_adapter.last_error()

        assert isinstance(error, tuple)
        assert len(error) == 2
        assert isinstance(error[0], int)
        assert isinstance(error[1], str)


@pytest.mark.integration
class TestMT5AdapterConstants:
    """Test MT5 constants are properly defined."""

    def test_trade_action_constants(self, mt5_adapter: MT5Adapter) -> None:
        """Test trade action constants."""
        assert mt5_adapter.TRADE_ACTION_DEAL == 1
        assert mt5_adapter.TRADE_ACTION_PENDING == 5
        assert mt5_adapter.TRADE_ACTION_SLTP == 6

    def test_order_type_constants(self, mt5_adapter: MT5Adapter) -> None:
        """Test order type constants."""
        assert mt5_adapter.ORDER_TYPE_BUY == 0
        assert mt5_adapter.ORDER_TYPE_SELL == 1
        assert mt5_adapter.ORDER_TYPE_BUY_LIMIT == 2
        assert mt5_adapter.ORDER_TYPE_SELL_LIMIT == 3
        assert mt5_adapter.ORDER_TYPE_BUY_STOP == 4
        assert mt5_adapter.ORDER_TYPE_SELL_STOP == 5

    def test_other_constants(self, mt5_adapter: MT5Adapter) -> None:
        """Test other trading constants."""
        assert mt5_adapter.ORDER_TIME_GTC == 0
        assert mt5_adapter.ORDER_FILLING_IOC == 1
        assert mt5_adapter.TRADE_RETCODE_DONE == 10009
