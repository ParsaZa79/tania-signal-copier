"""
MetaTrader 5 Adapter for macOS
==============================
Provides MT5 interface using siliconmetatrader5 with Docker container.

Setup:
1. Install: brew install colima docker qemu lima lima-additional-guestagents
2. Start: colima start --arch x86_64 --vm-type=qemu --cpu 4 --memory 8
3. Run MT5 container from silicon-metatrader5 repo
4. Login via VNC at http://localhost:6081/vnc.html (password: 123456)
"""

import os
from typing import Any

from siliconmetatrader5 import MetaTrader5 as SiliconMT5  # type: ignore[import-untyped]


class MT5Adapter:
    """MetaTrader 5 adapter using siliconmetatrader5 + Docker."""

    # MT5 constants
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6  # Modify SL/TP of existing position
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        keepalive: bool = True,
    ) -> None:
        self.host = host or os.getenv("MT5_DOCKER_HOST", "localhost")
        self.port = port or int(os.getenv("MT5_DOCKER_PORT", "8001"))
        self.keepalive = keepalive
        self._client: SiliconMT5 | None = None

    def initialize(self) -> bool:
        """Initialize connection to MT5 Docker container."""
        try:
            self._client = SiliconMT5(
                host=self.host,
                port=self.port,
                keepalive=self.keepalive,
            )
            return self._client.ping()
        except Exception as e:
            print(f"MT5 initialization failed: {e}")
            return False

    def login(self, login: int, password: str, server: str) -> bool:
        """Verify MT5 connection (login handled via VNC in Docker)."""
        # siliconmetatrader5 handles login through the Docker container
        # The MT5 instance should already be logged in via the VNC interface
        _ = login, password, server  # Credentials used in Docker VNC login
        return self._client is not None and self._client.ping()

    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        if self._client:
            self._client.shutdown()
            self._client = None

    def last_error(self) -> tuple[int, str]:
        """Get last error (limited info available via Docker)."""
        return (0, "Check Docker container logs for details")

    def account_info(self) -> Any:
        """Get account information."""
        if self._client:
            return self._client.account_info()
        return None

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol information."""
        if self._client:
            return self._client.symbol_info(symbol)
        return None

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get current tick for symbol."""
        if self._client:
            return self._client.symbol_info_tick(symbol)
        return None

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Enable/disable symbol in Market Watch."""
        if self._client:
            return self._client.symbol_select(symbol, enable)
        return False

    def order_send(self, request: dict) -> Any:
        """Send trading order."""
        if self._client:
            return self._client.order_send(request)
        return None

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        """Get historical rates (use position-based for fresh data)."""
        if self._client:
            return self._client.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        return None

    def ping(self) -> bool:
        """Check if connection is alive."""
        if self._client:
            return self._client.ping()
        return False

    def positions_total(self) -> int:
        """Get total number of open positions."""
        if self._client:
            return self._client.positions_total()
        return 0

    def positions_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get open positions, optionally filtered by symbol or ticket."""
        if not self._client:
            return []
        if ticket is not None:
            result = self._client.positions_get(ticket=ticket)
        elif symbol is not None:
            result = self._client.positions_get(symbol=symbol)
        else:
            result = self._client.positions_get()
        return list(result) if result else []


def create_mt5_adapter(
    host: str | None = None,
    port: int | None = None,
) -> MT5Adapter:
    """Factory function to create MT5 adapter."""
    return MT5Adapter(host=host, port=port)
