"""
MT5 trade executor for the Telegram Signal Bot.

This module handles all MetaTrader 5 trade operations including
opening, modifying, and closing positions.

Includes automatic reconnection to handle connection drops gracefully.
"""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from tania_signal_copier.models import OrderType, TradeSignal
from tania_signal_copier.mt5_adapter import MT5Adapter, create_mt5_adapter

T = TypeVar("T")


def with_reconnect(method: Callable[..., T]) -> Callable[..., T]:
    """Decorator that ensures connection before executing a method.

    If connection is lost, attempts to reconnect before retrying the operation.
    """

    @wraps(method)
    def wrapper(self: "MT5Executor", *args: Any, **kwargs: Any) -> T:
        # First attempt
        if self._ensure_connected():
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                print(f"Operation failed: {e}, attempting reconnect...")
                self.connected = False

        # Reconnect and retry
        if self._reconnect():
            return method(self, *args, **kwargs)

        # Return appropriate failure based on method
        method_name = method.__name__
        if method_name in ("execute_signal", "modify_position", "close_position"):
            return {"success": False, "error": "Connection lost and reconnect failed"}  # type: ignore
        elif method_name == "get_account_balance":
            return 0.0  # type: ignore
        elif method_name in ("get_position", "get_symbol_info"):
            return None  # type: ignore
        elif method_name == "is_position_profitable":
            return False  # type: ignore
        elif method_name == "get_current_price":
            return None  # type: ignore
        else:
            return None  # type: ignore

    return wrapper


class MT5Executor:
    """Handles trade execution on MetaTrader 5.

    Provides high-level trading operations built on top of the MT5Adapter,
    including position management, risk calculations, and automatic reconnection.

    Attributes:
        connected: Whether successfully connected to MT5
        max_reconnect_attempts: Maximum number of reconnection attempts
        reconnect_delay: Delay in seconds between reconnection attempts
    """

    def __init__(
        self,
        login: int,
        password: str,
        server: str,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 2.0,
    ) -> None:
        """Initialize executor with MT5 credentials.

        Args:
            login: MT5 account login number
            password: MT5 account password
            server: MT5 broker server name
            max_reconnect_attempts: Max reconnection attempts (default: 5)
            reconnect_delay: Delay between reconnection attempts in seconds (default: 2.0)
        """
        self._login = login
        self._password = password
        self._server = server
        self._mt5: MT5Adapter | None = None
        self.connected = False
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self._last_ping_time: float = 0
        self._ping_interval: float = 30.0  # Check connection every 30 seconds

    def connect(self) -> bool:
        """Initialize and connect to MT5.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._mt5 = create_mt5_adapter()
        except RuntimeError as e:
            print(f"MT5 adapter creation failed: {e}")
            return False

        if not self._mt5.initialize():
            print(f"MT5 initialize failed: {self._mt5.last_error()}")
            return False

        if not self._mt5.login(self._login, password=self._password, server=self._server):
            print(f"MT5 login failed: {self._mt5.last_error()}")
            self._mt5.shutdown()
            return False

        self.connected = True
        self._last_ping_time = time.time()
        account_info = self._mt5.account_info()
        if account_info:
            print(f"Connected to MT5: {account_info.name}, Balance: {account_info.balance}")
        else:
            print("Connected to MT5 (account info not available)")
        return True

    def disconnect(self) -> None:
        """Shutdown MT5 connection."""
        if self._mt5:
            self._mt5.shutdown()
        self.connected = False

    def is_alive(self) -> bool:
        """Check if the connection to MT5 is alive.

        Performs a ping to verify the connection is responsive.

        Returns:
            True if connection is alive, False otherwise
        """
        if not self._mt5 or not self.connected:
            return False
        try:
            return self._mt5.ping()
        except Exception:
            return False

    def _ensure_connected(self) -> bool:
        """Ensure we have an active connection, checking periodically.

        Returns:
            True if connected, False if connection check failed
        """
        if not self.connected or not self._mt5:
            return False

        # Only ping if enough time has passed since last check
        current_time = time.time()
        if current_time - self._last_ping_time >= self._ping_interval:
            if not self.is_alive():
                self.connected = False
                return False
            self._last_ping_time = current_time

        return True

    def _reconnect(self) -> bool:
        """Attempt to reconnect to MT5 with retries.

        Returns:
            True if reconnection successful, False otherwise
        """
        print("Attempting to reconnect to MT5...")

        # Clean up existing connection
        if self._mt5:
            try:
                self._mt5.shutdown()
            except Exception:
                pass
            self._mt5 = None
        self.connected = False

        for attempt in range(1, self.max_reconnect_attempts + 1):
            print(f"Reconnection attempt {attempt}/{self.max_reconnect_attempts}...")

            if self.connect():
                print("Reconnection successful!")
                return True

            if attempt < self.max_reconnect_attempts:
                print(f"Reconnection failed, waiting {self.reconnect_delay}s before retry...")
                time.sleep(self.reconnect_delay)

        print("All reconnection attempts failed!")
        return False

    def health_check(self) -> dict:
        """Perform a comprehensive health check of the MT5 connection.

        Returns:
            Dict with health status information
        """
        status = {
            "connected": self.connected,
            "ping_ok": False,
            "account_accessible": False,
            "trading_enabled": False,
            "account_balance": 0.0,
            "error": None,
        }

        if not self._mt5 or not self.connected:
            status["error"] = "Not connected"
            return status

        try:
            # Check ping
            status["ping_ok"] = self._mt5.ping()

            # Check account info
            account = self._mt5.account_info()
            if account:
                status["account_accessible"] = True
                status["account_balance"] = account.balance
                status["trading_enabled"] = account.trade_allowed

        except Exception as e:
            status["error"] = str(e)

        return status

    @with_reconnect
    def get_account_balance(self) -> float:
        """Get current account balance.

        Auto-reconnects if connection is lost.

        Returns:
            Account balance or 0.0 if unavailable
        """
        if not self._mt5:
            return 0.0
        info = self._mt5.account_info()
        return info.balance if info else 0.0

    @with_reconnect
    def get_symbol_info(self, symbol: str) -> dict | None:
        """Get symbol information, trying common variations.

        Auto-reconnects if connection is lost.

        Args:
            symbol: The trading symbol (e.g., "XAUUSD")

        Returns:
            Dict with 'info' and 'symbol' keys, or None if not found
        """
        if not self._mt5:
            return None

        info = self._mt5.symbol_info(symbol)
        if info is None:
            # Try common variations
            variations = [symbol, f"{symbol}.r", f"{symbol}m", f"{symbol}_"]
            for var in variations:
                info = self._mt5.symbol_info(var)
                if info:
                    return {"info": info, "symbol": var}
            return None
        return {"info": info, "symbol": symbol}

    @with_reconnect
    def get_position(self, ticket: int) -> dict | None:
        """Get position details by ticket number.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 position ticket

        Returns:
            Position dict with ticket, symbol, type, volume, etc., or None
        """
        if not self._mt5:
            return None

        positions = self._mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            return {
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": pos.type,
                "volume": pos.volume,
                "price_open": pos.price_open,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
            }
        return None

    @with_reconnect
    def is_position_profitable(self, ticket: int) -> bool:
        """Check if position is in profit.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 position ticket

        Returns:
            True if profit >= 0, False otherwise or if not found
        """
        pos = self.get_position(ticket)
        if pos is None:
            return False
        return pos["profit"] >= 0

    @with_reconnect
    def execute_signal(
        self,
        signal: TradeSignal,
        lot_size: float | None = None,
        broker_symbol: str | None = None,
        default_lot_size: float = 0.01,
    ) -> dict:
        """Execute a trade signal on MT5.

        Auto-reconnects if connection is lost.

        Args:
            signal: The parsed trade signal
            lot_size: Override lot size (optional)
            broker_symbol: Broker-specific symbol name (optional)
            default_lot_size: Default lot size if not specified

        Returns:
            Result dict with 'success' key and trade details or 'error'
        """
        if not self.connected or not self._mt5:
            return {"success": False, "error": "Not connected to MT5"}

        # Resolve symbol
        symbol_to_find = broker_symbol or signal.symbol
        sym_data = self.get_symbol_info(symbol_to_find)
        if not sym_data:
            return {"success": False, "error": f"Symbol {symbol_to_find} not found"}

        symbol = sym_data["symbol"]
        symbol_info = sym_data["info"]

        # Ensure symbol is visible in Market Watch
        if not symbol_info.visible:
            self._mt5.symbol_select(symbol, True)

        # Determine lot size
        lots = lot_size or signal.lot_size or default_lot_size
        lots = max(symbol_info.volume_min, min(lots, symbol_info.volume_max))

        # Get current prices
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": "Could not get current price"}

        # Build order request
        request = self._build_order_request(signal, symbol, lots, tick)
        print(f"    [DEBUG] Execute request: {request}")

        # Verify connection before sending
        if not self._mt5.ping():
            print("    [DEBUG] Connection lost before execute, attempting reconnect...")
            if not self._reconnect():
                return {"success": False, "error": "Connection lost and reconnect failed"}

        # Check order first to get detailed validation
        check_result = self._mt5.order_check(request)
        print(f"    [DEBUG] order_check result: {check_result}")

        # Send the order
        result = self._mt5.order_send(request)
        print(f"    [DEBUG] order_send result: {result}")

        if result is None:
            last_error = self._mt5.last_error()
            print(f"    [DEBUG] Last error: {last_error}")
            return {
                "success": False,
                "error": f"Order send failed (None), last_error: {last_error}",
                "retcode": -1,
            }

        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result.comment else f"Retcode {result.retcode}"
            print(f"    [DEBUG] Order failed - retcode: {result.retcode}, comment: {result.comment}")
            return {
                "success": False,
                "error": f"Order failed: {error_msg}",
                "retcode": result.retcode,
            }

        return {
            "success": True,
            "ticket": result.order,
            "volume": lots,
            "price": result.price,
            "symbol": symbol,
        }

    def _build_order_request(
        self,
        signal: TradeSignal,
        symbol: str,
        lots: float,
        tick,  # type: ignore[no-untyped-def]
    ) -> dict:
        """Build the MT5 order request dictionary.

        Requires self._mt5 to be initialized (caller must check).
        """
        assert self._mt5 is not None  # Caller ensures this

        is_buy = signal.order_type in [OrderType.BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]

        # Determine filling mode from symbol info
        sym_info = self._mt5.symbol_info(symbol)
        if sym_info and sym_info.filling_mode & 1:  # FOK supported
            filling_mode = self._mt5.ORDER_FILLING_FOK
        elif sym_info and sym_info.filling_mode & 2:  # IOC supported
            filling_mode = self._mt5.ORDER_FILLING_IOC
        else:
            filling_mode = self._mt5.ORDER_FILLING_RETURN

        request: dict = {
            "action": int(self._mt5.TRADE_ACTION_DEAL),
            "symbol": str(symbol),
            "volume": float(lots),
            "type": int(self._mt5.ORDER_TYPE_BUY if signal.order_type == OrderType.BUY else self._mt5.ORDER_TYPE_SELL),
            "price": float(tick.ask if is_buy else tick.bid),
            "deviation": 20,
            "magic": 123456,
            "comment": "TG Signal Bot",
            "type_time": int(self._mt5.ORDER_TIME_GTC),
            "type_filling": int(filling_mode),
        }

        # Add SL/TP (ensure floats and normalize to symbol digits)
        digits = sym_info.digits if sym_info else 2
        if signal.stop_loss:
            request["sl"] = round(float(signal.stop_loss), digits)
        if signal.take_profits:
            # Use the least profitable (closest) TP: highest for SELL, lowest for BUY
            best_tp = max(signal.take_profits) if not is_buy else min(signal.take_profits)
            request["tp"] = round(float(best_tp), digits)

        # Handle pending orders
        if signal.order_type in [
            OrderType.BUY_LIMIT,
            OrderType.SELL_LIMIT,
            OrderType.BUY_STOP,
            OrderType.SELL_STOP,
        ]:
            request["action"] = int(self._mt5.TRADE_ACTION_PENDING)

            # Ensure entry price is properly rounded to symbol digits
            entry_price = float(signal.entry_price) if signal.entry_price else float(tick.ask if is_buy else tick.bid)
            request["price"] = float(round(entry_price, digits))

            type_map = {
                OrderType.BUY_LIMIT: self._mt5.ORDER_TYPE_BUY_LIMIT,
                OrderType.SELL_LIMIT: self._mt5.ORDER_TYPE_SELL_LIMIT,
                OrderType.BUY_STOP: self._mt5.ORDER_TYPE_BUY_STOP,
                OrderType.SELL_STOP: self._mt5.ORDER_TYPE_SELL_STOP,
            }
            request["type"] = int(type_map[signal.order_type])

            # Remove deviation for pending orders (not applicable)
            request.pop("deviation", None)

            # Use RETURN filling mode for pending orders (most compatible)
            request["type_filling"] = int(self._mt5.ORDER_FILLING_RETURN)

        return request

    @with_reconnect
    def modify_position(
        self,
        ticket: int,
        sl: float | None = None,
        tp: float | None = None,
    ) -> dict:
        """Modify SL/TP of an existing position.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 position ticket
            sl: New stop loss price (optional)
            tp: New take profit price (optional)

        Returns:
            Result dict with 'success' key
        """
        if not self.connected or not self._mt5:
            return {"success": False, "error": "Not connected to MT5"}

        pos = self.get_position(ticket)
        if not pos:
            return {"success": False, "error": f"Position {ticket} not found"}

        new_sl = float(sl) if sl is not None else pos["sl"]
        new_tp = float(tp) if tp is not None else pos["tp"]

        # Get symbol info for proper formatting
        sym_info = self._mt5.symbol_info(pos["symbol"])
        if sym_info:
            # Normalize SL/TP to proper decimal places
            digits = sym_info.digits
            new_sl = round(new_sl, digits)
            new_tp = round(new_tp, digits) if new_tp else 0.0

        # Ensure all values are proper types for MT5
        request = {
            "action": self._mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": str(pos["symbol"]),
            "volume": float(pos["volume"]),
            "sl": float(new_sl),
            "tp": float(new_tp),
            "magic": 123456,
        }

        print(f"    [DEBUG] Modify request: {request}")
        print(f"    [DEBUG] Position info: {pos}")

        # Verify connection before sending
        if not self._mt5.ping():
            print("    [DEBUG] Connection lost, attempting reconnect...")
            if not self._reconnect():
                return {"success": False, "error": "Connection lost and reconnect failed"}

        result = self._mt5.order_send(request)
        print(f"    [DEBUG] order_send result: {result}")

        if result is None:
            # Try to get more info about what went wrong
            last_error = self._mt5.last_error()
            print(f"    [DEBUG] Last error: {last_error}")
            return {"success": False, "error": f"order_send returned None, last_error: {last_error}"}

        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result.comment else f"Retcode {result.retcode}"
            print(f"    [DEBUG] Modify failed - retcode: {result.retcode}, comment: {result.comment}")
            return {
                "success": False,
                "error": error_msg,
                "retcode": result.retcode,
            }

        return {
            "success": True,
            "ticket": ticket,
            "new_sl": request["sl"],
            "new_tp": request["tp"],
        }

    @with_reconnect
    def close_position(self, ticket: int) -> dict:
        """Close an open position by placing opposite order.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 position ticket

        Returns:
            Result dict with 'success' key and close details
        """
        if not self.connected or not self._mt5:
            return {"success": False, "error": "Not connected to MT5"}

        pos = self.get_position(ticket)
        if not pos:
            return {"success": False, "error": f"Position {ticket} not found"}

        tick = self._mt5.symbol_info_tick(pos["symbol"])
        if not tick:
            return {"success": False, "error": "Could not get current price"}

        # Close by placing opposite order
        # type 0 = BUY, so we SELL to close; type 1 = SELL, so we BUY to close
        is_buy = pos["type"] == 0
        close_type = self._mt5.ORDER_TYPE_SELL if is_buy else self._mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask

        # Determine filling mode from symbol info
        sym_info = self._mt5.symbol_info(pos["symbol"])
        if sym_info and sym_info.filling_mode & 1:  # FOK supported
            filling_mode = self._mt5.ORDER_FILLING_FOK
        elif sym_info and sym_info.filling_mode & 2:  # IOC supported
            filling_mode = self._mt5.ORDER_FILLING_IOC
        else:
            filling_mode = self._mt5.ORDER_FILLING_RETURN

        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos["symbol"],
            "volume": pos["volume"],
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "TG Signal Bot Close",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else "Close failed"
            return {"success": False, "error": error_msg}

        return {"success": True, "ticket": ticket, "closed_at": price}

    def calculate_default_sl(
        self,
        symbol: str,
        order_type: OrderType,
        entry_price: float,
        lot_size: float,
        max_risk_percent: float = 0.10,
    ) -> float:
        """Calculate default SL based on percentage of balance risk.

        Args:
            symbol: The trading symbol
            order_type: Buy or Sell direction
            entry_price: The entry price
            lot_size: The position lot size
            max_risk_percent: Maximum risk as fraction of balance (default 10%)

        Returns:
            Calculated stop loss price
        """
        balance = self.get_account_balance()
        max_risk = balance * max_risk_percent

        # Get symbol info for point value
        sym_data = self.get_symbol_info(symbol)
        if not sym_data:
            # Fallback values
            fallback = 5.0 if "XAU" in symbol.upper() else 0.0050
            is_buy = order_type in [OrderType.BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]
            return entry_price - fallback if is_buy else entry_price + fallback

        symbol_info = sym_data["info"]
        point = symbol_info.point
        tick_value = symbol_info.trade_tick_value

        # Calculate SL distance
        if lot_size * tick_value > 0:
            sl_distance = (max_risk * point) / (lot_size * tick_value)
        else:
            sl_distance = 500 * point  # Fallback

        is_buy = order_type in [OrderType.BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]
        return entry_price - sl_distance if is_buy else entry_price + sl_distance

    @with_reconnect
    def get_current_price(self, symbol: str, for_buy: bool) -> float | None:
        """Get current ask (for buy) or bid (for sell) price.

        Auto-reconnects if connection is lost.

        Args:
            symbol: The trading symbol
            for_buy: True for ask price, False for bid price

        Returns:
            Current price or None if unavailable
        """
        if not self._mt5:
            return None
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return tick.ask if for_buy else tick.bid

    @with_reconnect
    def get_pending_orders(self, symbol: str | None = None) -> list[dict]:
        """Get pending orders, optionally filtered by symbol.

        Auto-reconnects if connection is lost.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of pending order dicts
        """
        if not self._mt5:
            return []

        if symbol:
            orders = self._mt5.orders_get(symbol=symbol)
        else:
            orders = self._mt5.orders_get()

        if not orders:
            return []

        return [
            {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order.type,
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "comment": order.comment,
            }
            for order in orders
        ]

    @with_reconnect
    def get_pending_order(self, ticket: int) -> dict | None:
        """Get pending order details by ticket number.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 order ticket

        Returns:
            Order dict or None if not found
        """
        if not self._mt5:
            return None

        orders = self._mt5.orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            order = orders[0]
            return {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order.type,
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "comment": order.comment,
            }
        return None

    @with_reconnect
    def cancel_pending_order(self, ticket: int) -> dict:
        """Cancel a pending order by ticket.

        Auto-reconnects if connection is lost.

        Args:
            ticket: The MT5 order ticket

        Returns:
            Result dict with 'success' key
        """
        if not self.connected or not self._mt5:
            return {"success": False, "error": "Not connected to MT5"}

        # Verify order exists
        order = self.get_pending_order(ticket)
        if not order:
            return {"success": False, "error": f"Pending order {ticket} not found"}

        request = {
            "action": self._mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }

        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else "Cancel failed"
            return {"success": False, "error": error_msg, "retcode": getattr(result, "retcode", None)}

        return {"success": True, "ticket": ticket}
