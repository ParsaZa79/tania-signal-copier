"""
MT5 trade executor for the Telegram Signal Bot.

This module handles all MetaTrader 5 trade operations including
opening, modifying, and closing positions.
"""

from tania_signal_copier.models import OrderType, TradeSignal
from tania_signal_copier.mt5_adapter import MT5Adapter, create_mt5_adapter


class MT5Executor:
    """Handles trade execution on MetaTrader 5.

    Provides high-level trading operations built on top of the MT5Adapter,
    including position management and risk calculations.

    Attributes:
        connected: Whether successfully connected to MT5
    """

    def __init__(self, login: int, password: str, server: str) -> None:
        """Initialize executor with MT5 credentials.

        Args:
            login: MT5 account login number
            password: MT5 account password
            server: MT5 broker server name
        """
        self._login = login
        self._password = password
        self._server = server
        self._mt5: MT5Adapter | None = None
        self.connected = False

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

    def get_account_balance(self) -> float:
        """Get current account balance.

        Returns:
            Account balance or 0.0 if unavailable
        """
        if not self._mt5:
            return 0.0
        info = self._mt5.account_info()
        return info.balance if info else 0.0

    def get_symbol_info(self, symbol: str) -> dict | None:
        """Get symbol information, trying common variations.

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

    def get_position(self, ticket: int) -> dict | None:
        """Get position details by ticket number.

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

    def is_position_profitable(self, ticket: int) -> bool:
        """Check if position is in profit.

        Args:
            ticket: The MT5 position ticket

        Returns:
            True if profit >= 0, False otherwise or if not found
        """
        pos = self.get_position(ticket)
        if pos is None:
            return False
        return pos["profit"] >= 0

    def execute_signal(
        self,
        signal: TradeSignal,
        lot_size: float | None = None,
        broker_symbol: str | None = None,
        default_lot_size: float = 0.01,
    ) -> dict:
        """Execute a trade signal on MT5.

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

        # Send the order
        result = self._mt5.order_send(request)

        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else "Order send failed"
            retcode = result.retcode if result else -1
            return {
                "success": False,
                "error": f"Order failed: {error_msg}",
                "retcode": retcode,
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

        request: dict = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": self._mt5.ORDER_TYPE_BUY if signal.order_type == OrderType.BUY else self._mt5.ORDER_TYPE_SELL,
            "price": tick.ask if is_buy else tick.bid,
            "deviation": 20,
            "magic": 123456,
            "comment": "TG Signal Bot",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }

        # Add SL/TP
        if signal.stop_loss:
            request["sl"] = signal.stop_loss
        if signal.take_profits:
            request["tp"] = signal.take_profits[0]

        # Handle pending orders
        if signal.order_type in [
            OrderType.BUY_LIMIT,
            OrderType.SELL_LIMIT,
            OrderType.BUY_STOP,
            OrderType.SELL_STOP,
        ]:
            request["action"] = self._mt5.TRADE_ACTION_PENDING
            request["price"] = signal.entry_price

            type_map = {
                OrderType.BUY_LIMIT: self._mt5.ORDER_TYPE_BUY_LIMIT,
                OrderType.SELL_LIMIT: self._mt5.ORDER_TYPE_SELL_LIMIT,
                OrderType.BUY_STOP: self._mt5.ORDER_TYPE_BUY_STOP,
                OrderType.SELL_STOP: self._mt5.ORDER_TYPE_SELL_STOP,
            }
            request["type"] = type_map[signal.order_type]

        return request

    def modify_position(
        self,
        ticket: int,
        sl: float | None = None,
        tp: float | None = None,
    ) -> dict:
        """Modify SL/TP of an existing position.

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

        request = {
            "action": self._mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": pos["symbol"],
            "sl": sl if sl is not None else pos["sl"],
            "tp": tp if tp is not None else pos["tp"],
        }

        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else "Modify failed"
            return {"success": False, "error": error_msg}

        return {
            "success": True,
            "ticket": ticket,
            "new_sl": request["sl"],
            "new_tp": request["tp"],
        }

    def close_position(self, ticket: int) -> dict:
        """Close an open position by placing opposite order.

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
            "type_filling": self._mt5.ORDER_FILLING_IOC,
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

    def get_current_price(self, symbol: str, for_buy: bool) -> float | None:
        """Get current ask (for buy) or bid (for sell) price.

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
