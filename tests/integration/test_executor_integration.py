"""
Integration tests for MT5Executor.

Tests the high-level trading executor against a real MT5 Docker container.
Includes tests for order execution, position management, and risk calculations.

WARNING: Some tests may place real orders on a live account.
Use a demo account for testing!

Run with: pytest tests/integration/test_executor_integration.py -v
"""

import pytest

from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import OrderType, TradeSignal


@pytest.mark.integration
class TestMT5ExecutorConnection:
    """Test MT5Executor connection management."""

    def test_connect_success(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test successful connection."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        try:
            result = executor.connect()
            assert result is True
            assert executor.connected is True
        finally:
            executor.disconnect()

    def test_disconnect(self, mt5_executor: MT5Executor) -> None:
        """Test disconnection sets connected to False."""
        assert mt5_executor.connected is True

        mt5_executor.disconnect()

        assert mt5_executor.connected is False

    def test_connect_sets_internal_adapter(self, mt5_executor: MT5Executor) -> None:
        """Test that connect creates internal MT5 adapter."""
        assert mt5_executor._mt5 is not None


@pytest.mark.integration
class TestMT5ExecutorAccountOperations:
    """Test account-related operations."""

    def test_get_account_balance(self, mt5_executor: MT5Executor) -> None:
        """Test getting account balance."""
        balance = mt5_executor.get_account_balance()

        assert isinstance(balance, float)
        assert balance >= 0

    def test_get_account_balance_not_connected(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test balance returns 0 when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )
        # Not connected

        balance = executor.get_account_balance()

        assert balance == 0.0


@pytest.mark.integration
class TestMT5ExecutorSymbolOperations:
    """Test symbol-related operations."""

    def test_get_symbol_info_valid(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test getting info for valid symbol."""
        result = mt5_executor.get_symbol_info(test_symbol)

        assert result is not None
        assert "info" in result
        assert "symbol" in result
        assert result["symbol"] == test_symbol

    def test_get_symbol_info_with_variation(self, mt5_executor: MT5Executor) -> None:
        """Test symbol lookup tries variations."""
        # This tests the variation lookup logic
        # May or may not find a match depending on broker
        result = mt5_executor.get_symbol_info("EURUSD")

        # If found, should have correct structure
        if result is not None:
            assert "info" in result
            assert "symbol" in result

    def test_get_symbol_info_invalid(self, mt5_executor: MT5Executor) -> None:
        """Test invalid symbol returns None."""
        result = mt5_executor.get_symbol_info("TOTALLY_FAKE_SYMBOL")

        assert result is None

    def test_get_current_price_bid(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test getting bid price."""
        price = mt5_executor.get_current_price(test_symbol, for_buy=False)

        assert price is not None
        assert price > 0

    def test_get_current_price_ask(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test getting ask price."""
        price = mt5_executor.get_current_price(test_symbol, for_buy=True)

        assert price is not None
        assert price > 0

    def test_spread_is_reasonable(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test that spread (ask - bid) is positive."""
        ask = mt5_executor.get_current_price(test_symbol, for_buy=True)
        bid = mt5_executor.get_current_price(test_symbol, for_buy=False)

        assert ask is not None
        assert bid is not None
        assert ask >= bid, "Ask should be >= bid"


@pytest.mark.integration
class TestMT5ExecutorRiskCalculations:
    """Test risk calculation methods."""

    def test_calculate_default_sl_buy(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test default SL calculation for BUY order."""
        price = mt5_executor.get_current_price(test_symbol, for_buy=True)
        assert price is not None

        sl = mt5_executor.calculate_default_sl(
            symbol=test_symbol,
            order_type=OrderType.BUY,
            entry_price=price,
            lot_size=0.01,
            max_risk_percent=0.10,
        )

        assert sl is not None
        assert sl < price, "SL for BUY should be below entry"

    def test_calculate_default_sl_sell(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test default SL calculation for SELL order."""
        price = mt5_executor.get_current_price(test_symbol, for_buy=False)
        assert price is not None

        sl = mt5_executor.calculate_default_sl(
            symbol=test_symbol,
            order_type=OrderType.SELL,
            entry_price=price,
            lot_size=0.01,
            max_risk_percent=0.10,
        )

        assert sl is not None
        assert sl > price, "SL for SELL should be above entry"

    def test_calculate_default_sl_fallback(self, mt5_executor: MT5Executor) -> None:
        """Test SL calculation uses fallback for unknown symbol."""
        sl = mt5_executor.calculate_default_sl(
            symbol="UNKNOWN_SYMBOL",
            order_type=OrderType.BUY,
            entry_price=1.0000,
            lot_size=0.01,
            max_risk_percent=0.10,
        )

        # Should return a fallback value, not None
        assert sl is not None
        assert sl < 1.0000


@pytest.mark.integration
class TestMT5ExecutorPositionQueries:
    """Test position query methods."""

    def test_get_position_invalid_ticket(self, mt5_executor: MT5Executor) -> None:
        """Test getting non-existent position returns None."""
        result = mt5_executor.get_position(ticket=999999999)

        assert result is None

    def test_is_position_profitable_invalid_ticket(
        self, mt5_executor: MT5Executor
    ) -> None:
        """Test profitability check for non-existent position."""
        result = mt5_executor.is_position_profitable(ticket=999999999)

        assert result is False


@pytest.mark.integration
@pytest.mark.slow
class TestMT5ExecutorSignalExecution:
    """Test signal execution (actually places orders).

    WARNING: These tests place real orders! Use demo account only!
    Marked as slow because they involve actual trade execution.
    """

    def test_execute_signal_not_connected(self, mt5_credentials: dict) -> None:
        """Test execution fails when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )
        # Not connected

        signal = TradeSignal(
            symbol="EURUSD",
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            lot_size=0.01,
        )

        result = executor.execute_signal(signal)

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_execute_signal_invalid_symbol(self, mt5_executor: MT5Executor) -> None:
        """Test execution fails with invalid symbol."""
        signal = TradeSignal(
            symbol="TOTALLY_INVALID_SYMBOL",
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            lot_size=0.01,
        )

        result = mt5_executor.execute_signal(signal)

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_execute_buy_signal(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test executing a BUY market order.

        WARNING: This test places a real order!
        """
        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            lot_size=0.01,
            comment="Integration test BUY",
        )

        result = mt5_executor.execute_signal(signal)

        assert result["success"] is True
        assert "ticket" in result
        assert result["ticket"] > 0
        assert result["volume"] == 0.01

        # Clean up: close the position
        close_result = mt5_executor.close_position(result["ticket"])
        assert close_result["success"] is True

    def test_execute_sell_signal(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test executing a SELL market order.

        WARNING: This test places a real order!
        """
        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.SELL,
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            lot_size=0.01,
            comment="Integration test SELL",
        )

        result = mt5_executor.execute_signal(signal)

        assert result["success"] is True
        assert "ticket" in result

        # Clean up
        mt5_executor.close_position(result["ticket"])

    def test_execute_signal_with_sl_tp(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test executing order with SL and TP.

        WARNING: This test places a real order!
        """
        # Get current price to set reasonable SL/TP
        price = mt5_executor.get_current_price(test_symbol, for_buy=True)
        sym_data = mt5_executor.get_symbol_info(test_symbol)
        assert sym_data is not None
        point = sym_data["info"].point

        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=price - (100 * point),  # 100 points below
            take_profits=[price + (100 * point)],  # 100 points above
            lot_size=0.01,
            comment="Integration test with SL/TP",
        )

        result = mt5_executor.execute_signal(signal)

        assert result["success"] is True

        # Verify position has SL/TP
        pos = mt5_executor.get_position(result["ticket"])
        assert pos is not None
        assert pos["sl"] > 0
        assert pos["tp"] > 0

        # Clean up
        mt5_executor.close_position(result["ticket"])


@pytest.mark.integration
@pytest.mark.slow
class TestMT5ExecutorPositionManagement:
    """Test position modification and closure.

    WARNING: These tests may place real orders!
    """

    def test_modify_position_not_connected(self, mt5_credentials: dict) -> None:
        """Test modify fails when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        result = executor.modify_position(ticket=123, sl=1.0)

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_modify_position_invalid_ticket(self, mt5_executor: MT5Executor) -> None:
        """Test modify fails with invalid ticket."""
        result = mt5_executor.modify_position(
            ticket=999999999,
            sl=1.0,
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_close_position_not_connected(self, mt5_credentials: dict) -> None:
        """Test close fails when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        result = executor.close_position(ticket=123)

        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_close_position_invalid_ticket(self, mt5_executor: MT5Executor) -> None:
        """Test close fails with invalid ticket."""
        result = mt5_executor.close_position(ticket=999999999)

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_full_trade_lifecycle(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test complete trade lifecycle: open -> modify -> close.

        WARNING: This test places a real order!
        """
        # Step 1: Open position
        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            take_profits=[],
            lot_size=0.01,
            comment="Lifecycle test",
        )

        open_result = mt5_executor.execute_signal(signal)
        assert open_result["success"] is True
        ticket = open_result["ticket"]

        try:
            # Step 2: Verify position exists
            pos = mt5_executor.get_position(ticket)
            assert pos is not None
            assert pos["ticket"] == ticket

            # Step 3: Modify SL
            entry_price = pos["price_open"]
            sym_data = mt5_executor.get_symbol_info(test_symbol)
            assert sym_data is not None
            point = sym_data["info"].point
            new_sl = entry_price - (50 * point)

            modify_result = mt5_executor.modify_position(ticket, sl=new_sl)
            assert modify_result["success"] is True

            # Step 4: Verify modification
            pos = mt5_executor.get_position(ticket)
            assert pos is not None
            assert pos["sl"] == pytest.approx(new_sl, rel=1e-5)

        finally:
            # Step 5: Close position
            close_result = mt5_executor.close_position(ticket)
            assert close_result["success"] is True

            # Step 6: Verify closed
            pos = mt5_executor.get_position(ticket)
            assert pos is None
