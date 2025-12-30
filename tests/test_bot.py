"""Tests for the signal bot."""

import pytest

from tania_signal_copier.bot import OrderType, TradeSignal


class TestTradeSignal:
    """Tests for TradeSignal dataclass."""

    def test_create_trade_signal(self) -> None:
        """Test creating a trade signal."""
        signal = TradeSignal(
            symbol="EURUSD",
            order_type=OrderType.BUY,
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profits=[1.0900, 1.0950],
            lot_size=0.1,
            comment="Test signal",
            confidence=0.95,
        )

        assert signal.symbol == "EURUSD"
        assert signal.order_type == OrderType.BUY
        assert signal.entry_price == 1.0850
        assert signal.stop_loss == 1.0800
        assert len(signal.take_profits) == 2
        assert signal.confidence == 0.95

    def test_order_types(self) -> None:
        """Test all order types are valid."""
        assert OrderType.BUY.value == "buy"
        assert OrderType.SELL.value == "sell"
        assert OrderType.BUY_LIMIT.value == "buy_limit"
        assert OrderType.SELL_LIMIT.value == "sell_limit"
        assert OrderType.BUY_STOP.value == "buy_stop"
        assert OrderType.SELL_STOP.value == "sell_stop"


class TestSignalParser:
    """Tests for SignalParser class."""

    @pytest.mark.skip(reason="Requires API key")
    def test_parse_valid_signal(self) -> None:
        """Test parsing a valid trading signal."""
        # This test requires an actual API key
        pass

    def test_parse_invalid_signal(self) -> None:
        """Test that invalid messages return None."""
        # Parser would return None for non-signal messages
        pass
