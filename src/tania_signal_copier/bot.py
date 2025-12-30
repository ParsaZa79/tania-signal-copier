"""
Telegram to MetaTrader 5 Signal Bot
====================================
Automates forex trading by reading signals from Telegram and executing on MT5.

Requirements:
- Docker with siliconmetatrader5 container running (macOS)
- Telegram API credentials (api_id, api_hash from https://my.telegram.org)
- Claude Code CLI installed and authenticated (uses subscription auth)
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, TextBlock
from dotenv import load_dotenv
from telethon import TelegramClient, events

from tania_signal_copier.mt5_adapter import MT5Adapter, create_mt5_adapter

load_dotenv()


# ============== Configuration ==============


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Telegram settings
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_CHANNEL: str = os.getenv("TELEGRAM_CHANNEL", "")  # Channel username or ID

    # MT5 settings
    MT5_LOGIN: int = int(os.getenv("MT5_LOGIN", "0"))
    MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER: str = os.getenv("MT5_SERVER", "")

    # Trading settings
    DEFAULT_LOT_SIZE: float = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
    MAX_RISK_PERCENT: float = float(os.getenv("MAX_RISK_PERCENT", "2.0"))

    # Symbol settings
    ALLOWED_SYMBOLS: list[str] = field(default_factory=lambda: ["XAUUSD"])
    SYMBOL_MAP: dict[str, str] = field(default_factory=lambda: {"XAUUSD": "XAUUSDb"})


config = Config()


# ============== Data Models ==============


class OrderType(Enum):
    """Trading order types."""

    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


@dataclass
class TradeSignal:
    """Parsed trade signal from Telegram."""

    symbol: str  # e.g., "EURUSD", "XAUUSD"
    order_type: OrderType  # buy, sell, buy_limit, etc.
    entry_price: float | None  # Entry price (None for market orders)
    stop_loss: float | None  # Stop loss price
    take_profits: list[float]  # List of take profit levels
    lot_size: float | None  # Lot size (if specified)
    comment: str  # Original signal text
    confidence: float  # Parser confidence (0-1)


# ============== Signal Parser using Claude ==============


class SignalParser:
    """Uses Claude to parse trading signals from various formats."""

    def __init__(self) -> None:
        """Initialize parser. Uses Claude Code subscription auth (no API key needed)."""
        pass

    async def parse_signal(self, message: str) -> TradeSignal | None:
        """Parse a Telegram message into a structured trade signal."""
        prompt = f"""Analyze this forex trading signal and extract the trade details.
Return a JSON object with these fields:
- symbol: The trading pair (e.g., "EURUSD", "XAUUSD", "GBPJPY"). Normalize to uppercase without slashes.
- order_type: One of "buy", "sell", "buy_limit", "sell_limit", "buy_stop", "sell_stop"
- entry_price: The entry price as a number, or null for market execution
- stop_loss: The stop loss price as a number, or null if not specified
- take_profits: Array of take profit prices as numbers
- lot_size: Lot size as a number, or null if not specified
- confidence: Your confidence in the parsing from 0 to 1

If this is NOT a valid trading signal, return {{"is_signal": false}}

Signal message:
```
{message}
```

Return ONLY valid JSON, no explanation."""

        try:
            options = ClaudeAgentOptions(
                allowed_tools=[],  # No tools needed for parsing
                max_turns=1,  # Single turn for parsing
            )

            result_text = ""
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            result_text += block.text

            result_text = result_text.strip()
            # Clean up potential markdown code blocks
            result_text = re.sub(r"^```json\s*", "", result_text)
            result_text = re.sub(r"\s*```$", "", result_text)

            data = json.loads(result_text)

            if data.get("is_signal") is False:
                return None

            return TradeSignal(
                symbol=data["symbol"],
                order_type=OrderType(data["order_type"]),
                entry_price=data.get("entry_price"),
                stop_loss=data.get("stop_loss"),
                take_profits=data.get("take_profits", []),
                lot_size=data.get("lot_size"),
                comment=message[:200],
                confidence=data.get("confidence", 0.5),
            )

        except Exception as e:
            print(f"Error parsing signal: {e}")
            return None


# ============== MetaTrader 5 Executor ==============


class MT5Executor:
    """Handles trade execution on MetaTrader 5."""

    def __init__(self, login: int, password: str, server: str) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self._mt5: MT5Adapter | None = None

    def connect(self) -> bool:
        """Initialize and connect to MT5."""
        try:
            self._mt5 = create_mt5_adapter()
        except RuntimeError as e:
            print(f"MT5 adapter creation failed: {e}")
            return False

        if not self._mt5.initialize():
            print(f"MT5 initialize failed: {self._mt5.last_error()}")
            return False

        if not self._mt5.login(self.login, password=self.password, server=self.server):
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

    def get_symbol_info(self, symbol: str) -> dict | None:
        """Get symbol information."""
        if not self._mt5:
            return None

        info = self._mt5.symbol_info(symbol)
        if info is None:
            # Try common variations
            variations = [
                symbol,
                symbol + ".r",  # Some brokers add suffixes
                symbol + "m",
                symbol + "_",
            ]
            for var in variations:
                info = self._mt5.symbol_info(var)
                if info:
                    return {"info": info, "symbol": var}
            return None
        return {"info": info, "symbol": symbol}

    def execute_signal(
        self,
        signal: TradeSignal,
        lot_size: float | None = None,
        broker_symbol: str | None = None,
    ) -> dict:
        """Execute a trade signal on MT5."""
        if not self.connected or not self._mt5:
            return {"success": False, "error": "Not connected to MT5"}

        # Use broker symbol if provided, otherwise use signal symbol
        symbol_to_find = broker_symbol or signal.symbol

        # Get symbol info
        sym_data = self.get_symbol_info(symbol_to_find)
        if not sym_data:
            return {"success": False, "error": f"Symbol {symbol_to_find} not found"}

        symbol = sym_data["symbol"]
        symbol_info = sym_data["info"]

        # Ensure symbol is visible in Market Watch
        if not symbol_info.visible:
            self._mt5.symbol_select(symbol, True)

        # Determine lot size
        lots = lot_size or signal.lot_size or config.DEFAULT_LOT_SIZE
        lots = max(symbol_info.volume_min, min(lots, symbol_info.volume_max))

        # Get current prices
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": "Could not get current price"}

        # Prepare order request
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": self._mt5.ORDER_TYPE_BUY
            if signal.order_type == OrderType.BUY
            else self._mt5.ORDER_TYPE_SELL,
            "price": tick.ask if signal.order_type == OrderType.BUY else tick.bid,
            "deviation": 20,
            "magic": 123456,
            "comment": "TG Signal Bot",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }

        # Add stop loss if specified
        if signal.stop_loss:
            request["sl"] = signal.stop_loss

        # Add first take profit if specified
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


# ============== Main Bot ==============


class TelegramMT5Bot:
    """Main bot that connects Telegram signals to MT5."""

    def __init__(self) -> None:
        self.parser = SignalParser()
        self.executor = MT5Executor(
            config.MT5_LOGIN,
            config.MT5_PASSWORD,
            config.MT5_SERVER,
        )
        self.telegram = TelegramClient(
            "signal_bot_session",
            config.TELEGRAM_API_ID,
            config.TELEGRAM_API_HASH,
        )

        # Trade log
        self.trade_log: list[dict] = []

    async def start(self) -> None:
        """Start the bot."""
        print("Starting Telegram MT5 Signal Bot...")

        # Connect to MT5
        if not self.executor.connect():
            print("Failed to connect to MT5. Exiting.")
            return

        # Connect to Telegram
        await self.telegram.start()  # type: ignore[misc]
        print("Connected to Telegram")

        # Get the channel entity
        try:
            channel = await self.telegram.get_entity(config.TELEGRAM_CHANNEL)
            channel_name = getattr(channel, "title", config.TELEGRAM_CHANNEL)
            print(f"Monitoring channel: {channel_name}")
        except Exception as e:
            print(f"Could not find channel: {e}")
            return

        # Register message handler
        @self.telegram.on(events.NewMessage(chats=channel))
        async def handle_new_message(event: events.NewMessage.Event) -> None:
            await self.process_message(event.message.text)

        print("Bot is running! Waiting for signals...")
        await self.telegram.run_until_disconnected()  # type: ignore[misc]

    async def process_message(self, message: str) -> None:
        """Process an incoming Telegram message."""
        print(f"\n{'=' * 50}")
        print(f"New message received at {datetime.now()}")
        print(f"Message: {message[:100]}...")

        # Parse the signal
        signal = await self.parser.parse_signal(message)

        if signal is None:
            print("Not a valid trading signal, skipping.")
            return

        print("\nParsed Signal:")
        print(f"  Symbol: {signal.symbol}")
        print(f"  Type: {signal.order_type.value}")
        print(f"  Entry: {signal.entry_price or 'Market'}")
        print(f"  SL: {signal.stop_loss}")
        print(f"  TP: {signal.take_profits}")
        print(f"  Confidence: {signal.confidence:.0%}")

        # Check confidence threshold
        if signal.confidence < 0.7:
            print(f"Low confidence ({signal.confidence:.0%}), skipping execution.")
            return

        # Check if symbol is allowed
        if signal.symbol not in config.ALLOWED_SYMBOLS:
            print(f"Symbol {signal.symbol} not in allowed list {config.ALLOWED_SYMBOLS}, skipping.")
            return

        # Map symbol to broker-specific name
        broker_symbol = config.SYMBOL_MAP.get(signal.symbol, signal.symbol)
        if broker_symbol != signal.symbol:
            print(f"  Mapped to broker symbol: {broker_symbol}")

        # Execute the trade
        result = self.executor.execute_signal(signal, broker_symbol=broker_symbol)

        if result["success"]:
            print("\nTrade executed successfully!")
            print(f"  Ticket: {result['ticket']}")
            print(f"  Volume: {result['volume']}")
            print(f"  Price: {result['price']}")

            self.trade_log.append(
                {
                    "time": datetime.now().isoformat(),
                    "signal": signal.__dict__,
                    "result": result,
                }
            )
        else:
            print(f"\nTrade failed: {result['error']}")

    def stop(self) -> None:
        """Stop the bot and cleanup."""
        self.executor.disconnect()
        print("Bot stopped.")


# ============== Entry Point ==============


async def main() -> None:
    """Main entry point."""
    bot = TelegramMT5Bot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
