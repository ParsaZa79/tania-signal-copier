"""
Integration tests for progressive SL movement on TP hits.

Tests the new functionality that automatically moves SL when TPs are hit:
- TP1 hit -> SL moves to Entry
- TP2 hit -> SL moves to TP1
- TP3 hit -> SL moves to TP2

WARNING: These tests place real orders on MT5! Use a demo account only!

Run with: pytest tests/integration/test_progressive_sl.py -v
"""

from datetime import datetime

import pytest

from tania_signal_copier.bot import TelegramMT5Bot
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import (
    MessageType,
    OrderType,
    PositionStatus,
    TrackedPosition,
    TradeSignal,
)


@pytest.mark.integration
class TestProgressiveSLCalculation:
    """Test the progressive SL calculation logic."""

    @pytest.fixture
    def bot_instance(self) -> TelegramMT5Bot:
        """Create a bot instance for testing helper methods."""
        bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
        return bot

    def test_calculate_progressive_sl_tp1_returns_entry(
        self, bot_instance: TelegramMT5Bot
    ) -> None:
        """Test TP1 hit returns entry price for SL."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profits=[2660.0, 2670.0, 2680.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[],
        )

        result = bot_instance._calculate_progressive_sl(1, pos)

        assert result == 2650.0  # Entry price

    def test_calculate_progressive_sl_tp2_returns_tp1(
        self, bot_instance: TelegramMT5Bot
    ) -> None:
        """Test TP2 hit returns TP1 level for SL."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2650.0,  # Already at entry
            take_profits=[2660.0, 2670.0, 2680.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[1],
        )

        result = bot_instance._calculate_progressive_sl(2, pos)

        assert result == 2660.0  # TP1 level

    def test_calculate_progressive_sl_tp3_returns_tp2(
        self, bot_instance: TelegramMT5Bot
    ) -> None:
        """Test TP3 hit returns TP2 level for SL."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2660.0,  # At TP1
            take_profits=[2660.0, 2670.0, 2680.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[1, 2],
        )

        result = bot_instance._calculate_progressive_sl(3, pos)

        assert result == 2670.0  # TP2 level

    def test_calculate_progressive_sl_sell_order(
        self, bot_instance: TelegramMT5Bot
    ) -> None:
        """Test progressive SL for SELL order (TPs descending)."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.SELL,
            entry_price=2650.0,
            stop_loss=2660.0,
            take_profits=[2640.0, 2630.0, 2620.0],  # Descending for SELL
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[],
        )

        # TP1 -> Entry
        result1 = bot_instance._calculate_progressive_sl(1, pos)
        assert result1 == 2650.0

        # TP2 -> TP1 (2640)
        result2 = bot_instance._calculate_progressive_sl(2, pos)
        assert result2 == 2640.0

        # TP3 -> TP2 (2630)
        result3 = bot_instance._calculate_progressive_sl(3, pos)
        assert result3 == 2630.0


@pytest.mark.integration
class TestDetermineTPHit:
    """Test the TP hit determination logic."""

    @pytest.fixture
    def bot_instance(self) -> TelegramMT5Bot:
        """Create a bot instance for testing helper methods."""
        bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
        return bot

    @pytest.fixture
    def sample_position(self) -> TrackedPosition:
        """Create a sample position for testing."""
        return TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profits=[2660.0, 2670.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[],
        )

    def test_determine_tp_hit_from_signal(
        self, bot_instance: TelegramMT5Bot, sample_position: TrackedPosition
    ) -> None:
        """Test TP number extracted from signal takes priority."""
        signal = TradeSignal(
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            message_type=MessageType.PROFIT_NOTIFICATION,
            tp_hit_number=2,  # Explicitly says TP2
        )

        result = bot_instance._determine_tp_hit(signal, sample_position)

        assert result == 2

    def test_determine_tp_hit_from_move_sl_flag(
        self, bot_instance: TelegramMT5Bot, sample_position: TrackedPosition
    ) -> None:
        """Test move_sl_to_entry implies TP1."""
        signal = TradeSignal(
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            message_type=MessageType.PROFIT_NOTIFICATION,
            move_sl_to_entry=True,
            tp_hit_number=None,
        )

        result = bot_instance._determine_tp_hit(signal, sample_position)

        assert result == 1

    def test_determine_tp_hit_infers_next(
        self, bot_instance: TelegramMT5Bot
    ) -> None:
        """Test inference of next TP from already hit TPs."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2650.0,
            take_profits=[2660.0, 2670.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[1],  # TP1 already hit
        )

        signal = TradeSignal(
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=None,
            message_type=MessageType.PROFIT_NOTIFICATION,
            tp_hit_number=None,
            move_sl_to_entry=False,
        )

        result = bot_instance._determine_tp_hit(signal, pos)

        assert result == 2  # Next in sequence


@pytest.mark.integration
@pytest.mark.slow
class TestProgressiveSLOnRealMT5:
    """Test progressive SL modification on real MT5 positions.

    WARNING: These tests place real orders! Use demo account only!
    """

    def test_open_position_with_tps_and_modify_sl(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test opening a position and progressively modifying SL.

        This simulates the full flow:
        1. Open position with entry, SL, and multiple TPs
        2. Modify SL to entry (simulating TP1 hit)
        3. Modify SL to TP1 level (simulating TP2 hit)
        4. Close position
        """
        # Get current price to set reasonable SL/TP
        price = mt5_executor.get_current_price(test_symbol, for_buy=True)
        if price is None:
            pytest.skip("Could not get current price")

        sym_data = mt5_executor.get_symbol_info(test_symbol)
        assert sym_data is not None
        point = sym_data["info"].point

        # Calculate SL/TP levels
        sl_distance = 500 * point  # 50 pips for forex
        tp1_distance = 300 * point  # 30 pips
        tp2_distance = 600 * point  # 60 pips

        entry_price = price
        stop_loss = price - sl_distance
        tp1 = price + tp1_distance
        tp2 = price + tp2_distance

        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.BUY,
            entry_price=None,
            stop_loss=stop_loss,
            take_profits=[tp1, tp2],
            lot_size=0.01,
            comment="Progressive SL test",
        )

        # Step 1: Open position
        result = mt5_executor.execute_signal(signal)

        if not result["success"]:
            if "Market closed" in result.get("error", ""):
                pytest.skip("Market is closed")
            pytest.fail(f"Failed to open position: {result['error']}")

        ticket = result["ticket"]
        actual_entry = result["price"]
        print(f"\nOpened position {ticket} at {actual_entry}")
        print(f"  SL: {stop_loss}, TP1: {tp1}, TP2: {tp2}")

        try:
            # Verify position opened
            pos = mt5_executor.get_position(ticket)
            assert pos is not None
            assert pos["sl"] == pytest.approx(stop_loss, rel=0.001)

            # Step 2: Simulate TP1 hit - move SL to entry
            print(f"\nSimulating TP1 hit: Moving SL to entry ({actual_entry})")
            modify_result = mt5_executor.modify_position(ticket, sl=actual_entry)
            assert modify_result["success"], f"Modify failed: {modify_result['error']}"

            pos = mt5_executor.get_position(ticket)
            assert pos["sl"] == pytest.approx(actual_entry, rel=0.001)
            print(f"  SL now at: {pos['sl']}")

            # Step 3: Simulate TP2 hit - move SL to TP1
            print(f"\nSimulating TP2 hit: Moving SL to TP1 ({tp1})")
            modify_result = mt5_executor.modify_position(ticket, sl=tp1)
            assert modify_result["success"], f"Modify failed: {modify_result['error']}"

            pos = mt5_executor.get_position(ticket)
            assert pos["sl"] == pytest.approx(tp1, rel=0.001)
            print(f"  SL now at: {pos['sl']}")

        finally:
            # Clean up: close the position
            close_result = mt5_executor.close_position(ticket)
            print(f"\nClosed position: {close_result}")
            assert close_result["success"], f"Close failed: {close_result['error']}"

    def test_sell_position_progressive_sl(
        self, mt5_executor: MT5Executor, test_symbol: str
    ) -> None:
        """Test progressive SL for SELL order.

        For SELL orders:
        - Entry is high, TPs are below
        - SL moves down (more protective = lower for SELL)
        """
        price = mt5_executor.get_current_price(test_symbol, for_buy=False)
        if price is None:
            pytest.skip("Could not get current price")

        sym_data = mt5_executor.get_symbol_info(test_symbol)
        assert sym_data is not None
        point = sym_data["info"].point

        sl_distance = 500 * point
        tp1_distance = 300 * point
        tp2_distance = 600 * point

        entry_price = price
        stop_loss = price + sl_distance  # SL above for SELL
        tp1 = price - tp1_distance  # TP below for SELL
        tp2 = price - tp2_distance

        signal = TradeSignal(
            symbol=test_symbol,
            order_type=OrderType.SELL,
            entry_price=None,
            stop_loss=stop_loss,
            take_profits=[tp1, tp2],
            lot_size=0.01,
            comment="Progressive SL SELL test",
        )

        result = mt5_executor.execute_signal(signal)

        if not result["success"]:
            if "Market closed" in result.get("error", ""):
                pytest.skip("Market is closed")
            pytest.fail(f"Failed to open position: {result['error']}")

        ticket = result["ticket"]
        actual_entry = result["price"]
        print(f"\nOpened SELL position {ticket} at {actual_entry}")

        try:
            # TP1 hit - move SL to entry
            print(f"\nSimulating TP1 hit: Moving SL to entry ({actual_entry})")
            modify_result = mt5_executor.modify_position(ticket, sl=actual_entry)
            assert modify_result["success"]

            pos = mt5_executor.get_position(ticket)
            assert pos["sl"] == pytest.approx(actual_entry, rel=0.001)

            # TP2 hit - move SL to TP1 (which is below entry for SELL)
            print(f"\nSimulating TP2 hit: Moving SL to TP1 ({tp1})")
            modify_result = mt5_executor.modify_position(ticket, sl=tp1)
            assert modify_result["success"]

            pos = mt5_executor.get_position(ticket)
            assert pos["sl"] == pytest.approx(tp1, rel=0.001)

        finally:
            close_result = mt5_executor.close_position(ticket)
            assert close_result["success"]


@pytest.mark.integration
class TestTPsHitTracking:
    """Test that tps_hit list is properly tracked."""

    def test_tps_hit_serialization(self) -> None:
        """Test tps_hit is properly serialized and deserialized."""
        pos = TrackedPosition(
            telegram_msg_id=123,
            mt5_ticket=456,
            symbol="XAUUSD",
            order_type=OrderType.BUY,
            entry_price=2650.0,
            stop_loss=2650.0,
            take_profits=[2660.0, 2670.0],
            lot_size=0.01,
            opened_at=datetime.now(),
            is_complete=True,
            status=PositionStatus.OPEN,
            tps_hit=[1, 2],
        )

        # Serialize
        data = pos.to_dict()
        assert "tps_hit" in data
        assert data["tps_hit"] == [1, 2]

        # Deserialize
        restored = TrackedPosition.from_dict(data)
        assert restored.tps_hit == [1, 2]

    def test_tps_hit_default_empty(self) -> None:
        """Test tps_hit defaults to empty list for old state files."""
        data = {
            "telegram_msg_id": 123,
            "mt5_ticket": 456,
            "symbol": "XAUUSD",
            "order_type": "buy",
            "entry_price": 2650.0,
            "stop_loss": 2640.0,
            "take_profits": [2660.0],
            "lot_size": 0.01,
            "opened_at": datetime.now().isoformat(),
            "is_complete": True,
            "status": "open",
            # Note: no tps_hit field (simulating old state file)
        }

        restored = TrackedPosition.from_dict(data)
        assert restored.tps_hit == []
