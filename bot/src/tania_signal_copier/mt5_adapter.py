"""
MetaTrader 5 Adapter - Cross-Platform Support
==============================================
Provides MT5 interface with automatic platform detection:
- Windows: Uses native MetaTrader5 package (direct IPC with MT5 terminal)
- macOS: Uses siliconmetatrader5 with Docker container

Windows Setup:
1. Install MetaTrader 5 terminal from your broker
2. Run the bot - it will connect directly to the running terminal

macOS Setup:
1. Install: brew install colima docker qemu lima lima-additional-guestagents
2. Start: colima start --arch x86_64 --vm-type=qemu --cpu 4 --memory 8
3. Run MT5 container from silicon-metatrader5 repo
4. Login via VNC at http://localhost:6081/vnc.html (password: 123456)
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import Any

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


class MT5AdapterBase(ABC):
    """Abstract base class for MT5 adapters."""

    # MT5 constants (shared across all implementations)
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6  # Modify SL/TP of existing position
    TRADE_ACTION_REMOVE = 8  # Cancel pending order
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0  # Fill or Kill
    ORDER_FILLING_IOC = 1  # Immediate or Cancel
    ORDER_FILLING_RETURN = 2  # Return (partial fill)
    TRADE_RETCODE_DONE = 10009

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize connection to MT5."""
        ...

    @abstractmethod
    def login(self, login: int, password: str, server: str) -> bool:
        """Login to MT5 account."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        ...

    @abstractmethod
    def last_error(self) -> tuple[int, str]:
        """Get last error."""
        ...

    @abstractmethod
    def account_info(self) -> Any:
        """Get account information."""
        ...

    @abstractmethod
    def symbol_info(self, symbol: str) -> Any:
        """Get symbol information."""
        ...

    @abstractmethod
    def symbol_info_tick(self, symbol: str) -> Any:
        """Get current tick for symbol."""
        ...

    @abstractmethod
    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Enable/disable symbol in Market Watch."""
        ...

    @abstractmethod
    def order_check(self, request: dict) -> Any:
        """Check if order can be executed before sending."""
        ...

    @abstractmethod
    def order_send(self, request: dict) -> Any:
        """Send trading order."""
        ...

    @abstractmethod
    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        """Get historical rates."""
        ...

    @abstractmethod
    def ping(self) -> bool:
        """Check if connection is alive."""
        ...

    @abstractmethod
    def positions_total(self) -> int:
        """Get total number of open positions."""
        ...

    @abstractmethod
    def positions_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get open positions."""
        ...

    @abstractmethod
    def orders_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get pending orders."""
        ...

    @abstractmethod
    def history_deals_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        position: int | None = None,
    ) -> list[Any]:
        """Get history deals."""
        ...

    @abstractmethod
    def symbols_total(self) -> int:
        """Get total number of available symbols."""
        ...

    @abstractmethod
    def symbols_get(self, group: str | None = None) -> list[Any]:
        """Get all available symbols."""
        ...


class WindowsMT5Adapter(MT5AdapterBase):
    """MetaTrader 5 adapter for Windows using native MetaTrader5 package."""

    def __init__(
        self,
        path: str | None = None,
        timeout: int = 60000,
        portable: bool = False,
    ) -> None:
        """Initialize Windows MT5 adapter.

        Args:
            path: Path to MT5 terminal executable (optional, auto-detected if not set)
            timeout: Connection timeout in milliseconds
            portable: Whether to use portable mode
        """
        self.path = path or os.getenv("MT5_PATH")
        self.timeout = timeout
        self.portable = portable
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize connection to MT5 terminal."""
        try:
            import MetaTrader5 as mt5

            kwargs: dict[str, Any] = {"timeout": self.timeout, "portable": self.portable}
            if self.path:
                kwargs["path"] = self.path

            result = mt5.initialize(**kwargs)
            self._initialized = result
            return result
        except Exception as e:
            print(f"MT5 initialization failed: {e}")
            return False

    def login(self, login: int, password: str, server: str) -> bool:
        """Login to MT5 account.

        On Windows, this actually performs authentication with the MT5 terminal.
        """
        try:
            import MetaTrader5 as mt5

            return mt5.login(login, password=password, server=server)
        except Exception as e:
            print(f"MT5 login failed: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        try:
            import MetaTrader5 as mt5

            mt5.shutdown()
            self._initialized = False
        except Exception:
            pass

    def last_error(self) -> tuple[int, str]:
        """Get last error from MT5."""
        try:
            import MetaTrader5 as mt5

            return mt5.last_error()
        except Exception:
            return (-1, "Failed to get error")

    def account_info(self) -> Any:
        """Get account information."""
        try:
            import MetaTrader5 as mt5

            return mt5.account_info()
        except Exception:
            return None

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol information."""
        try:
            import MetaTrader5 as mt5

            return mt5.symbol_info(symbol)
        except Exception:
            return None

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get current tick for symbol."""
        try:
            import MetaTrader5 as mt5

            return mt5.symbol_info_tick(symbol)
        except Exception:
            return None

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Enable/disable symbol in Market Watch."""
        try:
            import MetaTrader5 as mt5

            return mt5.symbol_select(symbol, enable)
        except Exception:
            return False

    def order_check(self, request: dict) -> Any:
        """Check if order can be executed before sending."""
        try:
            import MetaTrader5 as mt5

            return mt5.order_check(request)
        except Exception:
            return None

    def order_send(self, request: dict) -> Any:
        """Send trading order."""
        try:
            import MetaTrader5 as mt5

            return mt5.order_send(request)
        except Exception:
            return None

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        """Get historical rates."""
        try:
            import MetaTrader5 as mt5

            return mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        except Exception:
            return None

    def ping(self) -> bool:
        """Check if connection is alive by getting terminal info."""
        try:
            import MetaTrader5 as mt5

            info = mt5.terminal_info()
            return info is not None
        except Exception:
            return False

    def positions_total(self) -> int:
        """Get total number of open positions."""
        try:
            import MetaTrader5 as mt5

            return mt5.positions_total()
        except Exception:
            return 0

    def positions_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get open positions."""
        try:
            import MetaTrader5 as mt5

            if ticket is not None:
                result = mt5.positions_get(ticket=ticket)
            elif symbol is not None:
                result = mt5.positions_get(symbol=symbol)
            else:
                result = mt5.positions_get()
            return list(result) if result else []
        except Exception:
            return []

    def orders_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get pending orders."""
        try:
            import MetaTrader5 as mt5

            if ticket is not None:
                result = mt5.orders_get(ticket=ticket)
            elif symbol is not None:
                result = mt5.orders_get(symbol=symbol)
            else:
                result = mt5.orders_get()
            return list(result) if result else []
        except Exception:
            return []

    def history_deals_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        position: int | None = None,
    ) -> list[Any]:
        """Get history deals."""
        try:
            import MetaTrader5 as mt5

            if position is not None:
                result = mt5.history_deals_get(position=position)
            elif date_from is not None and date_to is not None:
                result = mt5.history_deals_get(date_from, date_to)
            else:
                result = mt5.history_deals_get()
            return list(result) if result else []
        except Exception:
            return []

    def symbols_total(self) -> int:
        """Get total number of available symbols."""
        try:
            import MetaTrader5 as mt5

            return mt5.symbols_total()
        except Exception:
            return 0

    def symbols_get(self, group: str | None = None) -> list[Any]:
        """Get all available symbols."""
        try:
            import MetaTrader5 as mt5

            if group is not None:
                result = mt5.symbols_get(group=group)
            else:
                result = mt5.symbols_get()
            return list(result) if result else []
        except Exception:
            return []


class MacOSMT5Adapter(MT5AdapterBase):
    """MetaTrader 5 adapter for macOS using siliconmetatrader5 + Docker."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        keepalive: bool = True,
    ) -> None:
        self.host = host or os.getenv("MT5_DOCKER_HOST", "localhost")
        self.port = port or int(os.getenv("MT5_DOCKER_PORT", "8001"))
        self.keepalive = keepalive
        self._client: Any = None

    def initialize(self) -> bool:
        """Initialize connection to MT5 Docker container."""
        try:
            from siliconmetatrader5 import MetaTrader5 as SiliconMT5  # type: ignore[import-untyped]

            self._client = SiliconMT5(
                host=self.host,
                port=self.port,
                keepalive=self.keepalive,
            )
            return self._client.initialize()
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

    def order_check(self, request: dict) -> Any:
        """Check if order can be executed before sending."""
        if self._client:
            return self._client.order_check(request)
        return None

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

    def orders_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> list[Any]:
        """Get pending orders, optionally filtered by symbol or ticket."""
        if not self._client:
            return []
        if ticket is not None:
            result = self._client.orders_get(ticket=ticket)
        elif symbol is not None:
            result = self._client.orders_get(symbol=symbol)
        else:
            result = self._client.orders_get()
        return list(result) if result else []

    def history_deals_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        position: int | None = None,
    ) -> list[Any]:
        """Get history deals within date range or for specific position."""
        if not self._client:
            return []
        if position is not None:
            result = self._client.history_deals_get(position=position)
        elif date_from is not None and date_to is not None:
            result = self._client.history_deals_get(date_from, date_to)
        else:
            result = self._client.history_deals_get()
        return list(result) if result else []

    def symbols_total(self) -> int:
        """Get total number of available symbols."""
        if self._client:
            return self._client.symbols_total()
        return 0

    def symbols_get(self, group: str | None = None) -> list[Any]:
        """Get all available symbols, optionally filtered by group pattern."""
        if not self._client:
            return []
        if group is not None:
            result = self._client.symbols_get(group=group)
        else:
            result = self._client.symbols_get()
        return list(result) if result else []


# Type alias for backward compatibility
MT5Adapter = MT5AdapterBase


def create_mt5_adapter(
    host: str | None = None,
    port: int | None = None,
    path: str | None = None,
) -> MT5AdapterBase:
    """Factory function to create the appropriate MT5 adapter for the current platform.

    Args:
        host: Docker host (macOS only)
        port: Docker port (macOS only)
        path: Path to MT5 terminal executable (Windows only)

    Returns:
        Platform-appropriate MT5 adapter instance
    """
    if IS_WINDOWS:
        return WindowsMT5Adapter(path=path)
    elif IS_MACOS:
        return MacOSMT5Adapter(host=host, port=port)
    else:
        # Fallback to macOS adapter for other Unix-like systems (Linux with Docker)
        return MacOSMT5Adapter(host=host, port=port)
