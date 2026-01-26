"""
Trading strategy module for pluggable trade execution strategies.

This module provides an abstract base class for trading strategies and
concrete implementations for different trading approaches.
"""

from abc import ABC, abstractmethod
from enum import Enum

from .models import (
    DualPosition,
    MessageType,
    PositionStatus,
    TradeAction,
    TradeActionType,
    TradeConfig,
    TradeRole,
    TradeSignal,
)


class StrategyType(Enum):
    """Available trading strategies."""

    DUAL_TP = "dual_tp"  # Scalp (TP1) + Runner (last TP) with breakeven
    SINGLE = "single"  # Legacy single trade with TP1


class TradingStrategy(ABC):
    """Abstract base class for trading strategies.

    Strategies define how trades are opened, what actions to take on TP hits,
    and which messages to ignore.
    """

    @abstractmethod
    def get_trades_to_open(self, signal: TradeSignal) -> list[TradeConfig]:
        """Determine which trades to open for a given signal.

        Args:
            signal: The parsed trade signal

        Returns:
            List of TradeConfig objects describing trades to open
        """
        pass

    @abstractmethod
    def on_tp_hit(
        self, tp_number: int | None, dual: DualPosition, signal: TradeSignal
    ) -> list[TradeAction]:
        """Determine actions to take when a TP is hit.

        Args:
            tp_number: Which TP was hit (1, 2, 3...) or None if not specified
            dual: The dual position container
            signal: The profit notification signal

        Returns:
            List of TradeAction objects to execute
        """
        pass

    @abstractmethod
    def should_ignore_profit_message(self, signal: TradeSignal) -> bool:
        """Check if a profit notification should be ignored.

        Args:
            signal: The profit notification signal

        Returns:
            True if the message should be ignored, False otherwise
        """
        pass

    def is_re_entry(self, signal: TradeSignal) -> bool:
        """Check if signal is a re-entry (single trade only)."""
        return signal.message_type == MessageType.RE_ENTRY


class DualTPStrategy(TradingStrategy):
    """Dual-trade strategy: Scalp (TP1) + Runner (last TP).

    Behavior:
    - Opens two trades for each signal (complete or incomplete)
    - Scalp targets TP1, Runner targets the last TP (TP2, TP3, etc.)
    - On TP1 hit: Scalp closes, Runner moves SL to entry (breakeven)
    - Ignores "book profits" messages without explicit TP hit
    - Re-entry signals open single trade only
    """

    def get_trades_to_open(self, signal: TradeSignal) -> list[TradeConfig]:
        """Open two trades: Scalp with TP1, Runner with last TP.

        Always opens both trades for new signals (complete or incomplete).
        TPs will be set later for incomplete signals when completion arrives.
        """
        # Re-entry gets single trade
        if self.is_re_entry(signal):
            return [
                TradeConfig(
                    role=TradeRole.SINGLE,
                    tp=signal.take_profits[0] if signal.take_profits else None,
                    sl=signal.stop_loss,
                )
            ]

        trades = []

        # Scalp trade with TP1
        tp1 = signal.take_profits[0] if signal.take_profits else None
        trades.append(
            TradeConfig(
                role=TradeRole.SCALP,
                tp=tp1,
                sl=signal.stop_loss,
            )
        )

        # Runner trade with last TP (or None for incomplete signals)
        # Always open runner - TPs will be set when signal completes
        last_tp = signal.take_profits[-1] if len(signal.take_profits) >= 2 else None
        trades.append(
            TradeConfig(
                role=TradeRole.RUNNER,
                tp=last_tp,
                sl=signal.stop_loss,
            )
        )

        return trades

    def on_tp_hit(
        self, tp_number: int | None, dual: DualPosition, signal: TradeSignal
    ) -> list[TradeAction]:
        """Handle TP hit: close scalp, move runner to breakeven on TP1."""
        actions = []

        if tp_number == 1:
            # TP1 hit
            # Scalp: verify closed (MT5 auto-closes)
            if dual.scalp and dual.scalp.status != PositionStatus.CLOSED:
                actions.append(
                    TradeAction(
                        action_type=TradeActionType.VERIFY_CLOSED,
                        role=TradeRole.SCALP,
                    )
                )

            # Runner: move SL to entry (breakeven)
            if dual.runner and dual.runner.status != PositionStatus.CLOSED:
                actions.append(
                    TradeAction(
                        action_type=TradeActionType.MOVE_SL_TO_BREAKEVEN,
                        role=TradeRole.RUNNER,
                        value=dual.runner.entry_price,
                    )
                )

        elif tp_number is not None and tp_number > 1:
            # TP2+ hit - runner should be closed
            if dual.runner and dual.runner.status != PositionStatus.CLOSED:
                actions.append(
                    TradeAction(
                        action_type=TradeActionType.VERIFY_CLOSED,
                        role=TradeRole.RUNNER,
                    )
                )

        elif signal.move_sl_to_entry:
            # Explicit "move SL to entry" without TP number
            if dual.runner and dual.runner.status != PositionStatus.CLOSED:
                actions.append(
                    TradeAction(
                        action_type=TradeActionType.MOVE_SL_TO_BREAKEVEN,
                        role=TradeRole.RUNNER,
                        value=dual.runner.entry_price,
                    )
                )

        return actions

    def should_ignore_profit_message(self, signal: TradeSignal) -> bool:
        """Ignore 'book profits' messages without explicit TP hit."""
        # If no TP was explicitly hit and no move_sl_to_entry flag
        # This is just informational (e.g., "40 pips running, book some profits")
        return signal.tp_hit_number is None and not signal.move_sl_to_entry


class SingleTradeStrategy(TradingStrategy):
    """Legacy single-trade strategy: one trade with TP1.

    This is the original behavior before dual-trade support.
    """

    def get_trades_to_open(self, signal: TradeSignal) -> list[TradeConfig]:
        """Open single trade with TP1."""
        tp1 = signal.take_profits[0] if signal.take_profits else None
        return [
            TradeConfig(
                role=TradeRole.SINGLE,
                tp=tp1,
                sl=signal.stop_loss,
            )
        ]

    def on_tp_hit(
        self, tp_number: int | None, dual: DualPosition, signal: TradeSignal
    ) -> list[TradeAction]:
        """Verify trade closed on any TP hit."""
        actions = []

        if tp_number is not None:
            scalp = dual.scalp
            if scalp and scalp.status != PositionStatus.CLOSED:
                actions.append(
                    TradeAction(
                        action_type=TradeActionType.VERIFY_CLOSED,
                        role=TradeRole.SCALP,
                    )
                )

        return actions

    def should_ignore_profit_message(self, signal: TradeSignal) -> bool:
        """Ignore 'book profits' messages without explicit TP hit."""
        return signal.tp_hit_number is None and not signal.move_sl_to_entry


def get_strategy(strategy_type: str | StrategyType) -> TradingStrategy:
    """Factory function to get a trading strategy by type.

    Args:
        strategy_type: Strategy type as string or StrategyType enum

    Returns:
        TradingStrategy instance

    Raises:
        ValueError: If strategy type is unknown
    """
    if isinstance(strategy_type, str):
        try:
            strategy_type = StrategyType(strategy_type.lower())
        except ValueError as err:
            raise ValueError(f"Unknown strategy type: {strategy_type}") from err

    if strategy_type == StrategyType.DUAL_TP:
        return DualTPStrategy()
    elif strategy_type == StrategyType.SINGLE:
        return SingleTradeStrategy()
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
