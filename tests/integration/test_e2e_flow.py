"""
End-to-end integration test for the full signal flow.

This test:
1. Fetches the last 10 messages from the configured Telegram channel
2. Simulates realistic delays between processing each message
3. Parses signals using Claude AI
4. Attempts to execute trades on MT5 (handles market closed gracefully)

SETUP REQUIRED:
    First run: uv run python scripts/setup_telegram_session.py
    This creates the session file needed for authentication.

Run with: pytest tests/integration/test_e2e_flow.py -v -s

WARNING: This test uses real API calls (Telegram, Claude, MT5).
Use a demo MT5 account!
"""

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from telethon import TelegramClient

from tania_signal_copier.config import BotConfig, SymbolConfig
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import MessageType
from tania_signal_copier.parser import SignalParser

# Load environment variables
load_dotenv()

# Session file name (created by scripts/setup_telegram_session.py)
SESSION_NAME = "signal_bot_session"


def get_telegram_credentials() -> dict:
    """Get Telegram credentials from environment."""
    return {
        "api_id": int(os.getenv("TELEGRAM_API_ID", "0")),
        "api_hash": os.getenv("TELEGRAM_API_HASH", ""),
        "channel": os.getenv("TELEGRAM_CHANNEL", ""),
    }


def is_telegram_configured() -> bool:
    """Check if Telegram credentials are configured."""
    creds = get_telegram_credentials()
    return creds["api_id"] != 0 and creds["api_hash"] != "" and creds["channel"] != ""


def is_telegram_session_available() -> bool:
    """Check if Telegram session file exists."""
    session_file = Path(f"{SESSION_NAME}.session")
    return session_file.exists()


@pytest.fixture
def telegram_credentials() -> dict:
    """Fixture providing Telegram credentials."""
    return get_telegram_credentials()


@pytest.fixture
def bot_config() -> BotConfig:
    """Fixture providing bot configuration."""
    return BotConfig(
        symbols=SymbolConfig(
            allowed_symbols=["XAUUSD", "EURUSD", "GBPUSD"],
            symbol_map={
                "XAUUSD": os.getenv("TEST_SYMBOL", "XAUUSDb"),
                "EURUSD": "EURUSD",
                "GBPUSD": "GBPUSD",
            },
        )
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndFlow:
    """End-to-end test simulating the full trading flow."""

    @pytest.fixture
    def parser(self) -> SignalParser:
        """Create signal parser instance."""
        return SignalParser()

    @pytest.fixture
    def executor(self, mt5_credentials: dict, mt5_available: bool) -> MT5Executor:
        """Create connected MT5 executor."""
        exec_instance = MT5Executor(
            login=mt5_credentials["login"],
            password=mt5_credentials["password"],
            server=mt5_credentials["server"],
        )
        exec_instance.connect()
        yield exec_instance
        exec_instance.disconnect()

    async def test_fetch_and_process_last_10_messages(
        self,
        telegram_credentials: dict,
        parser: SignalParser,
        executor: MT5Executor,
        bot_config: BotConfig,
    ) -> None:
        """
        Full end-to-end test:
        1. Fetch last 10 messages from Telegram
        2. Parse each with simulated delay
        3. Execute trading signals on MT5
        """
        if not is_telegram_configured():
            pytest.skip("Telegram credentials not configured")

        if not is_telegram_session_available():
            pytest.skip(
                "Telegram session not found. Run: uv run python scripts/setup_telegram_session.py"
            )

        # Connect to Telegram using existing session
        client = TelegramClient(
            SESSION_NAME,
            telegram_credentials["api_id"],
            telegram_credentials["api_hash"],
        )

        await client.connect()
        if not await client.is_user_authorized():
            pytest.skip("Telegram session expired. Re-run: uv run python scripts/setup_telegram_session.py")
        print("\n" + "=" * 60)
        print("CONNECTED TO TELEGRAM")
        print("=" * 60)

        try:
            # Get channel entity
            channel = await client.get_entity(telegram_credentials["channel"])
            channel_name = getattr(channel, "title", telegram_credentials["channel"])
            print(f"Channel: {channel_name}")
            print("=" * 60)

            # Fetch last 10 messages
            messages = await client.get_messages(channel, limit=10)
            print(f"\nFetched {len(messages)} messages")
            print("=" * 60)

            # Process statistics
            stats = {
                "total": len(messages),
                "trading_signals": 0,
                "non_trading": 0,
                "executed": 0,
                "failed": 0,
                "skipped_market_closed": 0,
                "skipped_symbol": 0,
            }

            # Process each message with simulated delay
            for i, msg in enumerate(reversed(messages)):  # Process oldest first
                print(f"\n{'─' * 60}")
                print(f"MESSAGE {i + 1}/{len(messages)}")
                print(f"{'─' * 60}")
                print(f"ID: {msg.id}")
                print(f"Date: {msg.date}")
                print(f"Text: {(msg.text or '')[:150]}...")

                # Simulated delay (1-3 seconds between messages)
                delay = 1.0 + (i % 3) * 0.5
                print(f"\n⏳ Simulating {delay:.1f}s delay...")
                await asyncio.sleep(delay)

                # Skip empty messages
                if not msg.text:
                    print("⚪ Empty message, skipping")
                    stats["non_trading"] += 1
                    continue

                # Parse the message using Claude AI
                print("\n📊 Parsing with Claude AI...")
                try:
                    signal = await parser.parse_signal(msg.text)
                except Exception as e:
                    print(f"❌ Parse error: {e}")
                    stats["non_trading"] += 1
                    continue

                if signal is None:
                    print("⚪ Not a trading message")
                    stats["non_trading"] += 1
                    continue

                stats["trading_signals"] += 1
                print(f"\n✅ Parsed Signal:")
                print(f"   Type: {signal.message_type.value}")
                print(f"   Symbol: {signal.symbol}")
                print(f"   Order: {signal.order_type.value}")
                print(f"   Entry: {signal.entry_price}")
                print(f"   SL: {signal.stop_loss}")
                print(f"   TPs: {signal.take_profits}")
                print(f"   Confidence: {signal.confidence:.0%}")

                # Only execute NEW_SIGNAL_COMPLETE signals
                if signal.message_type not in [
                    MessageType.NEW_SIGNAL_COMPLETE,
                    MessageType.NEW_SIGNAL_INCOMPLETE,
                ]:
                    print(f"ℹ️  Not a new signal ({signal.message_type.value}), skipping execution")
                    continue

                # Check symbol allowlist
                if not bot_config.symbols.is_allowed(signal.symbol):
                    print(f"⚠️  Symbol {signal.symbol} not in allowed list, skipping")
                    stats["skipped_symbol"] += 1
                    continue

                # Get broker symbol
                broker_symbol = bot_config.symbols.get_broker_symbol(signal.symbol)
                print(f"\n🔄 Executing on MT5 (broker symbol: {broker_symbol})...")

                # Execute the trade
                result = executor.execute_signal(
                    signal,
                    broker_symbol=broker_symbol,
                    default_lot_size=0.01,
                )

                if result["success"]:
                    stats["executed"] += 1
                    print(f"✅ Trade executed!")
                    print(f"   Ticket: {result['ticket']}")
                    print(f"   Volume: {result['volume']}")
                    print(f"   Price: {result['price']}")

                    # Close the position immediately (this is a test)
                    print("🔄 Closing test position...")
                    close_result = executor.close_position(result["ticket"])
                    if close_result["success"]:
                        print(f"✅ Position closed at {close_result['closed_at']}")
                    else:
                        print(f"⚠️  Failed to close: {close_result['error']}")

                elif "Market closed" in result.get("error", ""):
                    stats["skipped_market_closed"] += 1
                    print(f"⏸️  Market closed, skipping execution")
                else:
                    stats["failed"] += 1
                    print(f"❌ Trade failed: {result['error']}")

            # Print final statistics
            print("\n" + "=" * 60)
            print("TEST COMPLETE - STATISTICS")
            print("=" * 60)
            print(f"Total messages:        {stats['total']}")
            print(f"Trading signals:       {stats['trading_signals']}")
            print(f"Non-trading:           {stats['non_trading']}")
            print(f"Executed:              {stats['executed']}")
            print(f"Failed:                {stats['failed']}")
            print(f"Skipped (mkt closed):  {stats['skipped_market_closed']}")
            print(f"Skipped (symbol):      {stats['skipped_symbol']}")
            print("=" * 60)

            # Assertions
            assert stats["total"] == len(messages)
            assert stats["trading_signals"] + stats["non_trading"] == stats["total"]

        finally:
            await client.disconnect()
            print("\nDisconnected from Telegram")

    async def test_parse_messages_only(
        self,
        telegram_credentials: dict,
        parser: SignalParser,
    ) -> None:
        """
        Lighter test that only fetches and parses messages without MT5 execution.
        Useful for testing the Telegram + Claude AI flow independently.
        """
        if not is_telegram_configured():
            pytest.skip("Telegram credentials not configured")

        if not is_telegram_session_available():
            pytest.skip(
                "Telegram session not found. Run: uv run python scripts/setup_telegram_session.py"
            )

        client = TelegramClient(
            SESSION_NAME,
            telegram_credentials["api_id"],
            telegram_credentials["api_hash"],
        )

        await client.connect()
        if not await client.is_user_authorized():
            pytest.skip("Telegram session expired. Re-run: uv run python scripts/setup_telegram_session.py")
        print("\n" + "=" * 60)
        print("PARSE-ONLY TEST")
        print("=" * 60)

        try:
            channel = await client.get_entity(telegram_credentials["channel"])
            messages = await client.get_messages(channel, limit=10)
            print(f"Fetched {len(messages)} messages\n")

            parsed_count = 0
            for i, msg in enumerate(reversed(messages)):
                if not msg.text:
                    continue

                print(f"Message {i + 1}: {msg.text[:80]}...")

                # Simulated delay
                await asyncio.sleep(0.5)

                try:
                    signal = await parser.parse_signal(msg.text)
                    if signal:
                        parsed_count += 1
                        print(f"  → {signal.message_type.value} | {signal.symbol} | {signal.order_type.value}")
                    else:
                        print(f"  → NOT_TRADING")
                except Exception as e:
                    print(f"  → ERROR: {e}")

            print(f"\nParsed {parsed_count} trading signals out of {len(messages)} messages")

        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
class TestTelegramConnection:
    """Test Telegram connection independently."""

    async def test_can_connect_and_fetch_messages(
        self,
        telegram_credentials: dict,
    ) -> None:
        """Test that we can connect to Telegram and fetch messages."""
        if not is_telegram_configured():
            pytest.skip("Telegram credentials not configured")

        if not is_telegram_session_available():
            pytest.skip(
                "Telegram session not found. Run: uv run python scripts/setup_telegram_session.py"
            )

        client = TelegramClient(
            SESSION_NAME,
            telegram_credentials["api_id"],
            telegram_credentials["api_hash"],
        )

        await client.connect()
        if not await client.is_user_authorized():
            pytest.skip("Telegram session expired. Re-run: uv run python scripts/setup_telegram_session.py")

        try:
            channel = await client.get_entity(telegram_credentials["channel"])
            messages = await client.get_messages(channel, limit=5)

            assert len(messages) > 0
            print(f"\n✅ Successfully fetched {len(messages)} messages from Telegram")

            # Print message preview
            for i, msg in enumerate(messages):
                text_preview = (msg.text or "")[:50] + "..." if msg.text else "(no text)"
                print(f"  {i + 1}. [{msg.date}] {text_preview}")

        finally:
            await client.disconnect()
