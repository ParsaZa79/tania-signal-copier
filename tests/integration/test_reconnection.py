"""
Integration tests for MT5Executor reconnection functionality.

Tests the reconnection mechanism, health checks, and connection resilience.

Run with: pytest tests/integration/test_reconnection.py -v
"""

import pytest

from tania_signal_copier.executor import MT5Executor


@pytest.mark.integration
class TestMT5ExecutorHealthCheck:
    """Test health check functionality."""

    def test_is_alive_when_connected(self, mt5_executor: MT5Executor) -> None:
        """Test is_alive returns True when connected."""
        assert mt5_executor.is_alive() is True

    def test_is_alive_when_not_connected(self, mt5_credentials: dict) -> None:
        """Test is_alive returns False when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )
        # Not connected

        assert executor.is_alive() is False

    def test_health_check_connected(self, mt5_executor: MT5Executor) -> None:
        """Test health_check returns proper status when connected."""
        status = mt5_executor.health_check()

        assert status["connected"] is True
        assert status["ping_ok"] is True
        assert status["account_accessible"] is True
        assert status["account_balance"] >= 0
        assert status["error"] is None

    def test_health_check_not_connected(self, mt5_credentials: dict) -> None:
        """Test health_check returns proper status when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        status = executor.health_check()

        assert status["connected"] is False
        assert status["ping_ok"] is False
        assert status["error"] == "Not connected"


@pytest.mark.integration
class TestMT5ExecutorReconnection:
    """Test reconnection functionality."""

    def test_reconnect_success(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test successful reconnection after disconnect."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
            max_reconnect_attempts=3,
            reconnect_delay=0.5,
        )

        try:
            # Connect first
            assert executor.connect() is True
            assert executor.connected is True

            # Disconnect
            executor.disconnect()
            assert executor.connected is False

            # Reconnect
            result = executor._reconnect()
            assert result is True
            assert executor.connected is True

        finally:
            executor.disconnect()

    def test_reconnect_restores_functionality(
        self, mt5_credentials: dict, mt5_available: bool, test_symbol: str
    ) -> None:
        """Test that reconnection restores full functionality."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        try:
            # Connect and verify working
            executor.connect()
            balance1 = executor.get_account_balance()
            assert balance1 > 0

            # Simulate disconnect
            executor.disconnect()
            assert executor.connected is False

            # Reconnect
            executor._reconnect()

            # Verify functionality restored
            balance2 = executor.get_account_balance()
            assert balance2 > 0
            assert balance2 == pytest.approx(balance1, rel=0.01)

            # Verify other operations work
            sym_info = executor.get_symbol_info(test_symbol)
            assert sym_info is not None

            price = executor.get_current_price(test_symbol, for_buy=True)
            assert price is not None and price > 0

        finally:
            executor.disconnect()

    def test_auto_reconnect_after_disconnect(
        self, mt5_credentials: dict, mt5_available: bool, test_symbol: str
    ) -> None:
        """Test that operations auto-reconnect after disconnect."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        try:
            # Connect first
            executor.connect()
            balance1 = executor.get_account_balance()
            assert balance1 > 0

            # Disconnect (simulating connection drop)
            executor.disconnect()
            assert executor.connected is False

            # Operations should auto-reconnect and succeed
            balance2 = executor.get_account_balance()
            assert balance2 > 0, "Auto-reconnect should restore balance access"
            assert executor.connected is True, "Should be reconnected now"

            sym_info = executor.get_symbol_info(test_symbol)
            assert sym_info is not None

        finally:
            executor.disconnect()


@pytest.mark.integration
class TestMT5ExecutorAutoReconnect:
    """Test automatic reconnection via the with_reconnect decorator."""

    def test_ensure_connected_when_alive(self, mt5_executor: MT5Executor) -> None:
        """Test _ensure_connected returns True when connection is good."""
        assert mt5_executor._ensure_connected() is True

    def test_ensure_connected_when_disconnected(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test _ensure_connected returns False when not connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        assert executor._ensure_connected() is False

    def test_operations_auto_reconnect_with_valid_credentials(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test that operations auto-reconnect when not initially connected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
            max_reconnect_attempts=3,
            reconnect_delay=0.5,
        )
        # Not connected initially

        try:
            # Operations should trigger auto-reconnect and succeed
            balance = executor.get_account_balance()
            assert balance > 0, "Should auto-reconnect and get balance"
            assert executor.connected is True
        finally:
            executor.disconnect()


@pytest.mark.integration
class TestMT5ExecutorConnectionConfig:
    """Test connection configuration options."""

    def test_custom_reconnect_attempts(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test custom max_reconnect_attempts is respected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
            max_reconnect_attempts=10,
        )

        assert executor.max_reconnect_attempts == 10

    def test_custom_reconnect_delay(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test custom reconnect_delay is respected."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
            reconnect_delay=5.0,
        )

        assert executor.reconnect_delay == 5.0

    def test_ping_interval_default(
        self, mt5_credentials: dict, mt5_available: bool
    ) -> None:
        """Test default ping interval is set."""
        executor = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )

        assert executor._ping_interval == 30.0
