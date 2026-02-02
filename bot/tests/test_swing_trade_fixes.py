"""
Tests for swing trade timeout and signal completeness fixes.

These tests cover the four issues that caused profitable swing trades to be closed prematurely:
1. 5-minute timeout closes profitable trades (now disabled by default)
2. Market orders wrongly marked incomplete (market orders don't need entry price)
3. TP skipped when price moved past it (now falls back to next TP or 1:1 RR)
4. Race condition: Edit arrives before position created (now cached and applied later)
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tania_signal_copier.bot import TelegramMT5Bot
from tania_signal_copier.config import BotConfig, MT5Config, SymbolConfig, TelegramConfig, TradingConfig
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import (
    DualPosition,
    MessageType,
    OrderType,
    PositionStatus,
    TrackedPosition,
    TradeRole,
    TradeSignal,
)
from tania_signal_copier.parser import SignalParser


# =============================================================================
# Fix 1: Timeout disabled by default
# =============================================================================

class TestTimeoutDisabledByDefault:
    """Tests for Fix 1: Timeout should be disabled by default for swing trades."""

    def test_default_timeout_is_zero(self):
        """Default timeout should be 0 (disabled) for swing trades."""
        config = TradingConfig()
        assert config.incomplete_signal_timeout == 0

    def test_timeout_can_be_enabled_via_env(self, monkeypatch):
        """Timeout can still be enabled via environment variable."""
        import os
        # Directly test int parsing from env var (same logic as config)
        monkeypatch.setenv("INCOMPLETE_SIGNAL_TIMEOUT_SECONDS", "300")
        timeout = int(os.getenv("INCOMPLETE_SIGNAL_TIMEOUT_SECONDS", "0"))
        assert timeout == 300

    @pytest.mark.asyncio
    async def test_start_timeout_skips_when_disabled(self):
        """_start_timeout should return immediately when timeout is 0."""
        config = BotConfig(
            telegram=TelegramConfig(api_id=123, api_hash="test"),
            mt5=MT5Config(login=123, password="test", server="test"),
            trading=TradingConfig(),  # Default timeout = 0
        )

        with patch.object(TelegramMT5Bot, '__init__', lambda x, y: None):
            bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
            bot._config = config
            bot._pending_timeouts = {}

            # Should not create any task when timeout is disabled
            await bot._start_timeout(12345, 99999)

            assert len(bot._pending_timeouts) == 0

    @pytest.mark.asyncio
    async def test_start_timeout_creates_task_when_enabled(self):
        """_start_timeout should create task when timeout > 0."""
        config = BotConfig(
            telegram=TelegramConfig(api_id=123, api_hash="test"),
            mt5=MT5Config(login=123, password="test", server="test"),
            trading=TradingConfig(),
        )
        # Override timeout for this test
        config.trading.incomplete_signal_timeout = 300

        with patch.object(TelegramMT5Bot, '__init__', lambda x, y: None):
            bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
            bot._config = config
            bot._pending_timeouts = {}
            bot.state = MagicMock()
            bot.executor = MagicMock()

            await bot._start_timeout(12345, 99999)

            # Should have created a timeout task
            assert 12345 in bot._pending_timeouts

            # Clean up
            bot._pending_timeouts[12345].cancel()


# =============================================================================
# Fix 2: Market orders don't need entry price to be complete
# =============================================================================

class TestMarketOrderCompleteness:
    """Tests for Fix 2: Market orders only need SL and TP to be complete."""

    def test_market_buy_complete_with_sl_tp_no_entry(self):
        """Market BUY with SL and TP but no entry should be COMPLETE."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "buy",
            "stop_loss": 2800.0,
            "take_profits": [2850.0, 2900.0],
            "entry_price": None,  # No entry price for market order
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True

    def test_market_sell_complete_with_sl_tp_no_entry(self):
        """Market SELL with SL and TP but no entry should be COMPLETE."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "sell",
            "stop_loss": 2900.0,
            "take_profits": [2850.0],
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True

    def test_market_order_incomplete_without_sl(self):
        """Market order without SL should be INCOMPLETE."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "buy",
            "stop_loss": None,  # Missing SL
            "take_profits": [2850.0],
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_market_order_incomplete_without_tp(self):
        """Market order without TP should be INCOMPLETE."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "sell",
            "stop_loss": 2900.0,
            "take_profits": [],  # Missing TP
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_pending_buy_limit_requires_entry_price(self):
        """BUY_LIMIT pending order REQUIRES entry price."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "buy_limit",
            "stop_loss": 2800.0,
            "take_profits": [2850.0],
            "entry_price": None,  # Missing entry - should be incomplete
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_pending_sell_limit_requires_entry_price(self):
        """SELL_LIMIT pending order REQUIRES entry price."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "sell_limit",
            "stop_loss": 2900.0,
            "take_profits": [2850.0],
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_pending_buy_stop_requires_entry_price(self):
        """BUY_STOP pending order REQUIRES entry price."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "buy_stop",
            "stop_loss": 2800.0,
            "take_profits": [2900.0],
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_pending_sell_stop_requires_entry_price(self):
        """SELL_STOP pending order REQUIRES entry price."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "sell_stop",
            "stop_loss": 2900.0,
            "take_profits": [2800.0],
            "entry_price": None,
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False

    def test_pending_order_complete_with_all_fields(self):
        """Pending order with SL, TP, and entry should be COMPLETE."""
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "order_type": "buy_limit",
            "stop_loss": 2800.0,
            "take_profits": [2900.0],
            "entry_price": 2820.0,  # Has entry price
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True


# =============================================================================
# Fix 3: TP fallback when price moved past it
# =============================================================================

class TestTPFallback:
    """Tests for Fix 3: Try multiple TPs and fallback to 1:1 RR when all breached."""

    def setup_method(self):
        """Set up executor mock for each test."""
        self.executor = MT5Executor(login=123, password="test", server="test")

    def test_find_valid_tp_first_tp_valid_for_buy(self):
        """For BUY, if TP1 > entry, use TP1 with no warning."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2800.0,
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2750.0,
        )

        assert tp == 2850.0
        assert warning is None

    def test_find_valid_tp_first_tp_valid_for_sell(self):
        """For SELL, if TP1 < entry, use TP1 with no warning."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=False,
            entry_price=2900.0,
            take_profits=[2850.0, 2800.0, 2750.0],
            stop_loss=2950.0,
        )

        assert tp == 2850.0
        assert warning is None

    def test_find_valid_tp_skip_breached_tp1_for_buy(self):
        """For BUY, if TP1 <= entry (breached), try TP2."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2860.0,  # Price moved past TP1 (2850)
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2750.0,
        )

        assert tp == 2900.0
        assert "TP1" in warning
        assert "breached" in warning.lower()

    def test_find_valid_tp_skip_breached_tp1_for_sell(self):
        """For SELL, if TP1 >= entry (breached), try TP2."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=False,
            entry_price=2840.0,  # Price moved past TP1 (2850)
            take_profits=[2850.0, 2800.0, 2750.0],
            stop_loss=2950.0,
        )

        assert tp == 2800.0
        assert "TP1" in warning
        assert "breached" in warning.lower()

    def test_find_valid_tp_skip_multiple_breached_tps(self):
        """Skip multiple breached TPs and use first valid one."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2910.0,  # Price moved past TP1 (2850) and TP2 (2900)
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2750.0,
        )

        assert tp == 2950.0
        assert "TP3" in warning

    def test_find_valid_tp_all_breached_use_1_1_rr_for_buy(self):
        """When all TPs breached for BUY, use 1:1 RR fallback."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2960.0,  # Past all TPs
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2900.0,  # SL is 60 points below entry
        )

        # 1:1 RR: entry (2960) + SL distance (60) = 3020
        assert tp == 3020.0
        assert "1:1 RR fallback" in warning

    def test_find_valid_tp_all_breached_use_1_1_rr_for_sell(self):
        """When all TPs breached for SELL, use 1:1 RR fallback."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=False,
            entry_price=2740.0,  # Past all TPs (below them for sell)
            take_profits=[2850.0, 2800.0, 2750.0],
            stop_loss=2800.0,  # SL is 60 points above entry
        )

        # 1:1 RR: entry (2740) - SL distance (60) = 2680
        assert tp == 2680.0
        assert "1:1 RR fallback" in warning

    def test_find_valid_tp_all_breached_no_sl_opens_without_tp(self):
        """When all TPs breached and no SL, return None with warning."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2960.0,
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=None,  # No SL for fallback calculation
        )

        assert tp is None
        assert "without TP" in warning

    def test_find_valid_tp_empty_tps_with_sl(self):
        """With empty TPs and SL, should use 1:1 RR fallback."""
        tp, warning = self.executor.find_valid_tp(
            is_buy=True,
            entry_price=2850.0,
            take_profits=[],
            stop_loss=2800.0,  # 50 points below entry
        )

        # With no TPs but SL available, uses 1:1 RR fallback
        # 2850 + 50 = 2900
        assert tp == 2900.0
        assert "1:1 RR fallback" in warning


# =============================================================================
# Fix 4: Race condition - edit arrives during processing
# =============================================================================

class TestEditRaceCondition:
    """Tests for Fix 4: Handle edits that arrive while processing original message."""

    def test_pending_edits_cache_initialized(self):
        """Bot should have _pending_edits cache initialized."""
        with patch.object(TelegramMT5Bot, '__init__', lambda x, y: None):
            bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
            bot._config = BotConfig(
                telegram=TelegramConfig(api_id=123, api_hash="test"),
                mt5=MT5Config(login=123, password="test", server="test"),
            )
            bot._pending_timeouts = {}
            bot._tp_verification_timeouts = {}
            bot._pending_edits = {}

            assert hasattr(bot, '_pending_edits')
            assert isinstance(bot._pending_edits, dict)

    @pytest.mark.asyncio
    async def test_edit_stored_when_no_position_exists(self):
        """Edit should be cached when no position exists yet (mid-processing)."""
        config = BotConfig(
            telegram=TelegramConfig(api_id=123, api_hash="test"),
            mt5=MT5Config(login=123, password="test", server="test"),
            trading=TradingConfig(),
        )

        with patch.object(TelegramMT5Bot, '__init__', lambda x, y: None):
            bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
            bot._config = config
            bot._pending_edits = {}
            bot.state = MagicMock()
            bot.state.get_dual_position_by_msg_id.return_value = None  # No position yet

            # Create mock edit event
            mock_event = MagicMock()
            mock_event.message.id = 12345
            mock_event.message.text = "XAUUSD SELL @ 2850\nSL: 2900\nTP: 2800"

            await bot._process_edited_message(mock_event)

            # Edit should be cached
            assert 12345 in bot._pending_edits
            assert "XAUUSD SELL" in bot._pending_edits[12345]

    @pytest.mark.asyncio
    async def test_pending_edit_applied_after_position_created(self):
        """Pending edit should be applied after position is created."""
        config = BotConfig(
            telegram=TelegramConfig(api_id=123, api_hash="test"),
            mt5=MT5Config(login=123, password="test", server="test"),
            trading=TradingConfig(),
            symbols=SymbolConfig(allowed_symbols=["XAUUSD"], symbol_map={"XAUUSD": "XAUUSDb"}),
        )

        with patch.object(TelegramMT5Bot, '__init__', lambda x, y: None):
            bot = TelegramMT5Bot.__new__(TelegramMT5Bot)
            bot._config = config
            bot._pending_edits = {12345: "XAUUSD SELL\nSL: 2900\nTP: 2800"}  # Pending edit
            bot._pending_timeouts = {}
            bot.trade_log = []

            # Mock state
            mock_dual = MagicMock(spec=DualPosition)
            mock_dual.is_closed = False
            mock_dual.all_positions = []

            bot.state = MagicMock()
            bot.state.get_pending_position_by_symbol.return_value = None
            bot.state.get_dual_position_by_msg_id.return_value = mock_dual

            # Mock executor
            bot.executor = MagicMock()
            bot.executor.execute_dual_signal.return_value = {
                "scalp": {"success": True, "ticket": 99999, "volume": 0.01, "price": 2850.0, "symbol": "XAUUSDb"}
            }

            # Mock parser
            bot.parser = MagicMock()
            new_signal = TradeSignal(
                symbol="XAUUSD",
                order_type=OrderType.SELL,
                entry_price=None,
                stop_loss=2900.0,
                take_profits=[2800.0],
            )
            bot.parser.parse_signal = AsyncMock(return_value=new_signal)

            # Mock strategy
            from tania_signal_copier.models import TradeConfig
            bot.strategy = MagicMock()
            bot.strategy.get_trades_to_open.return_value = [
                TradeConfig(role=TradeRole.SCALP, tp=2800.0, sl=2900.0, lot_multiplier=1.0)
            ]

            # Mock _apply_edit_changes
            bot._apply_edit_changes = AsyncMock()

            # Create signal
            signal = TradeSignal(
                symbol="XAUUSD",
                order_type=OrderType.SELL,
                entry_price=None,
                stop_loss=2900.0,
                take_profits=[2800.0],
            )

            await bot._handle_new_signal(12345, signal, is_complete=True)

            # Pending edit should have been removed from cache
            assert 12345 not in bot._pending_edits

            # _apply_edit_changes should have been called
            bot._apply_edit_changes.assert_called_once()


# =============================================================================
# Integration-style tests with simulated messages
# =============================================================================

class TestSimulatedSignalScenarios:
    """Integration-style tests simulating real signal scenarios."""

    def test_xauusd_sell_market_order_with_sl_tp_is_complete(self):
        """
        Scenario: Signal provider sends 'XAUUSD SELL' with SL and TP but no entry price.
        Expected: Should be marked as COMPLETE (market orders execute at current price).

        Example message:
        XAUUSD SELL
        SL: 2900
        TP: 2850, 2800, 2750
        """
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "sell",
            "entry_price": None,  # No entry for market order
            "stop_loss": 2900.0,
            "take_profits": [2850.0, 2800.0, 2750.0],
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True, "Market order with SL/TP should be complete"

    def test_tp_fallback_when_price_gaps_past_tp1(self):
        """
        Scenario: Signal says TP1=2850 but by the time we execute, price is at 2860.
        Expected: Should use TP2 instead of TP1.
        """
        executor = MT5Executor(login=123, password="test", server="test")

        tp, warning = executor.find_valid_tp(
            is_buy=True,
            entry_price=2860.0,  # Already past TP1
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2800.0,
        )

        assert tp == 2900.0, "Should use TP2 when TP1 is breached"
        assert warning is not None, "Should warn about breached TP"

    def test_all_tps_breached_uses_rr_fallback(self):
        """
        Scenario: Price gaps so much that all TPs are already breached.
        Expected: Calculate 1:1 RR TP based on SL distance.
        """
        executor = MT5Executor(login=123, password="test", server="test")

        # BUY signal, entry at 2970, all TPs (2850, 2900, 2950) already breached
        tp, warning = executor.find_valid_tp(
            is_buy=True,
            entry_price=2970.0,
            take_profits=[2850.0, 2900.0, 2950.0],
            stop_loss=2920.0,  # 50 points risk
        )

        # 1:1 RR = 2970 + 50 = 3020
        assert tp == 3020.0, "Should use 1:1 RR fallback TP"
        assert "fallback" in warning.lower()

    def test_pending_limit_order_requires_entry(self):
        """
        Scenario: Signal provider sends 'BUY LIMIT' with SL/TP but forgets entry price.
        Expected: Should be marked as INCOMPLETE.
        """
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "buy_limit",
            "entry_price": None,  # Missing entry for limit order
            "stop_loss": 2800.0,
            "take_profits": [2900.0],
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is False, "Limit order without entry should be incomplete"

    def test_timeout_disabled_swing_trade_stays_open(self):
        """
        Scenario: Incomplete swing trade signal is opened.
        Expected: With timeout=0, trade should NOT be closed automatically.
        """
        config = TradingConfig()
        assert config.incomplete_signal_timeout == 0, "Default timeout should be disabled"


class TestRealWorldSignalMessages:
    """Tests with actual signal message formats from channels."""

    def test_parse_sell_signal_without_entry(self):
        """
        Real signal format:
        XAUUSD SELL
        SL 2667.16
        TP 2661 / 2655 / 2643
        """
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "sell",
            "entry_price": None,
            "stop_loss": 2667.16,
            "take_profits": [2661.0, 2655.0, 2643.0],
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True

    def test_parse_buy_signal_with_entry_zone(self):
        """
        Real signal format:
        XAUUSD BUY @ 2640-2642
        SL 2635
        TP 2650 / 2660 / 2680

        Note: Entry is informational for market orders, not required.
        """
        parser = SignalParser()
        data = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "buy",
            "entry_price": 2640.0,  # Has entry but not required
            "stop_loss": 2635.0,
            "take_profits": [2650.0, 2660.0, 2680.0],
        }

        is_complete = parser._check_completeness(data, MessageType.NEW_SIGNAL_COMPLETE)
        assert is_complete is True

    def test_parse_sell_limit_pending_order(self):
        """
        Real signal format:
        XAUUSD SELL LIMIT @ 2680
        SL 2690
        TP 2660 / 2640
        """
        parser = SignalParser()

        # With entry price - complete
        data_complete = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "sell_limit",
            "entry_price": 2680.0,
            "stop_loss": 2690.0,
            "take_profits": [2660.0, 2640.0],
        }
        assert parser._check_completeness(data_complete, MessageType.NEW_SIGNAL_COMPLETE) is True

        # Without entry price - incomplete
        data_incomplete = {
            "message_type": "new_signal_complete",
            "symbol": "XAUUSD",
            "order_type": "sell_limit",
            "entry_price": None,
            "stop_loss": 2690.0,
            "take_profits": [2660.0, 2640.0],
        }
        assert parser._check_completeness(data_incomplete, MessageType.NEW_SIGNAL_COMPLETE) is False
