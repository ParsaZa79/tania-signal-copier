"""
Telegram to MetaTrader 5 Signal Bot
====================================

Main bot coordinator that connects Telegram signals to MT5 trading.

This module contains the TelegramMT5Bot class which:
- Monitors a Telegram channel for trading signals
- Parses signals using Claude AI
- Executes trades on MetaTrader 5
- Manages position state and timeouts

Requirements:
- Docker with siliconmetatrader5 container running (macOS)
- Telegram API credentials (api_id, api_hash from https://my.telegram.org)
- Claude Code CLI installed and authenticated
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from telethon import TelegramClient, events

from tania_signal_copier.config import BotConfig, config
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import (
    DualPosition,
    MessageType,
    OrderType,
    PositionStatus,
    TrackedPosition,
    TradeActionType,
    TradeRole,
    TradeSignal,
)
from tania_signal_copier.parser import SignalParser
from tania_signal_copier.state import BotState
from tania_signal_copier.strategy import TradingStrategy, get_strategy


class TelegramMT5Bot:
    """Main bot that connects Telegram signals to MT5.

    This class coordinates all components:
    - Telegram client for receiving messages
    - SignalParser for AI-powered message classification
    - MT5Executor for trade execution
    - BotState for position tracking
    - TradingStrategy for dual-trade or single-trade mode

    Attributes:
        parser: The signal parser instance
        executor: The MT5 executor instance
        state: The persistent state manager
        strategy: The trading strategy (dual_tp or single)
    """

    def __init__(self, bot_config: BotConfig | None = None) -> None:
        """Initialize the bot with configuration.

        Args:
            bot_config: Configuration object. Uses global config if not provided.
        """
        self._config = bot_config or config

        self.parser = SignalParser()
        self.executor = MT5Executor(
            login=self._config.mt5.login,
            password=self._config.mt5.password,
            server=self._config.mt5.server,
        )
        self.state = BotState(state_file=self._config.state_file)
        self.strategy: TradingStrategy = get_strategy(self._config.trading.strategy_type)
        print(f"Using trading strategy: {self._config.trading.strategy_type}")

        self._telegram = TelegramClient(
            self._config.telegram.session_name,
            self._config.telegram.api_id,
            self._config.telegram.api_hash,
        )

        # Timeout management
        self._pending_timeouts: dict[int, asyncio.Task] = {}
        # TP verification uses (msg_id, ticket) tuples as keys
        self._tp_verification_timeouts: dict[tuple[int, int], asyncio.Task] = {}

        # Trade log for history
        self.trade_log: list[dict] = []

        # Reconnection settings
        self._max_reconnect_attempts = 0  # 0 = infinite
        self._reconnect_delay = 10  # seconds between attempts
        self._max_reconnect_delay = 300  # max 5 minutes
        self._shutdown_requested = False
        self._handle_telegram_event: Callable[..., Any] | None = None
        self._handle_edit_event: Callable[..., Any] | None = None

    async def start(self) -> None:
        """Start the bot and begin monitoring the Telegram channel.

        Implements automatic reconnection with exponential backoff for network failures.
        """
        print("Starting Telegram MT5 Signal Bot...")

        # Load saved state
        self.state.load()
        print(f"Loaded {len(self.state)} tracked positions from state")

        # Connect to MT5
        if not self.executor.connect():
            print("Failed to connect to MT5. Exiting.")
            return

        # Run with reconnection loop
        await self._run_with_reconnection()

    async def _run_with_reconnection(self) -> None:
        """Main loop with automatic reconnection on network failures."""
        attempt = 0
        current_delay = self._reconnect_delay

        while not self._shutdown_requested:
            try:
                # Connect to Telegram
                await self._telegram.connect()

                if not await self._telegram.is_user_authorized():
                    await self._telegram.start()  # type: ignore[misc]

                print("Connected to Telegram")

                # Reset reconnection state on successful connection
                attempt = 0
                current_delay = self._reconnect_delay

                # Get the channel entity
                channel = await self._telegram.get_entity(self._config.telegram.channel)
                channel_name = getattr(channel, "title", self._config.telegram.channel)
                print(f"Monitoring channel: {channel_name}")

                # Register message handlers (remove old handlers first to avoid duplicates)
                if self._handle_telegram_event is not None:
                    self._telegram.remove_event_handler(self._handle_telegram_event)
                if self._handle_edit_event is not None:
                    self._telegram.remove_event_handler(self._handle_edit_event)

                @self._telegram.on(events.NewMessage(chats=channel))
                async def handle_new_message(event: events.NewMessage.Event) -> None:
                    await self._process_message(event)

                @self._telegram.on(events.MessageEdited(chats=channel))
                async def handle_edited_message(event: events.MessageEdited.Event) -> None:
                    await self._process_edited_message(event)

                # Store references for cleanup
                self._handle_telegram_event = handle_new_message
                self._handle_edit_event = handle_edited_message

                print("Bot is running! Waiting for signals...")
                await self._telegram.run_until_disconnected()  # type: ignore[misc]

                # If we get here, connection was lost
                if self._shutdown_requested:
                    break

                print("\nTelegram connection lost!")

            except (OSError, ConnectionError) as e:
                print(f"\nConnection error: {e}")

            except Exception as e:
                print(f"\nUnexpected error: {type(e).__name__}: {e}")

            # Check if we should retry
            if self._shutdown_requested:
                break

            attempt += 1
            if self._max_reconnect_attempts > 0 and attempt >= self._max_reconnect_attempts:
                print(f"\nMax reconnection attempts ({self._max_reconnect_attempts}) reached. Exiting.")
                break

            # Wait before reconnecting with exponential backoff
            print(f"Reconnecting in {current_delay} seconds... (attempt {attempt})")
            await asyncio.sleep(current_delay)

            # Exponential backoff with cap
            current_delay = min(current_delay * 2, self._max_reconnect_delay)

            # Ensure MT5 is still connected
            if not self.executor.is_alive():
                print("MT5 connection lost, reconnecting...")
                if not self.executor._reconnect():
                    print("Failed to reconnect to MT5")

        print("Reconnection loop ended.")

    async def _process_message(self, event: events.NewMessage.Event) -> None:
        """Process an incoming Telegram message.

        Routes the message to the appropriate handler based on its classification.
        """
        msg = event.message
        msg_id = msg.id
        reply_to_msg_id = msg.reply_to.reply_to_msg_id if msg.reply_to else None
        text = msg.text or ""

        self._log_message_received(msg_id, reply_to_msg_id, text)

        # Parse and classify
        signal = await self.parser.parse_signal(text)
        if signal is None:
            print("Not a trading message, skipping.")
            return

        self._log_signal_parsed(signal)

        # Check confidence threshold
        if signal.confidence < self._config.trading.min_confidence:
            print(f"Low confidence ({signal.confidence:.0%}), skipping.")
            return

        # Route to appropriate handler
        await self._route_signal(msg_id, reply_to_msg_id, signal)

    async def _process_edited_message(self, event: events.MessageEdited.Event) -> None:
        """Process an edited Telegram message.

        When a signal provider edits their original message (e.g., to fix a typo
        in SL/TP values), this method detects the change and updates MT5 positions.

        Safety checks:
        1. Only process edits for messages we have tracked positions for
        2. Only process if position is still open
        3. Only process if edit is within the configured time window
        """
        msg = event.message
        msg_id = msg.id
        text = msg.text or ""

        print(f"\n{'=' * 50}")
        print(f"EDIT DETECTED - Message ID: {msg_id}")
        print(f"New text: {text[:100]}...")

        # Safety check 1: Do we have a position for this message?
        dual = self.state.get_dual_position_by_msg_id(msg_id)
        if dual is None:
            print("No tracked position for this message, ignoring edit.")
            return

        # Safety check 2: Is position still open?
        if dual.is_closed:
            print("Position already closed, ignoring edit.")
            return

        # Safety check 3: Time window check
        edit_window = self._config.trading.edit_window_seconds
        oldest_position = min(p.opened_at for p in dual.all_positions)
        time_since_open = (datetime.now() - oldest_position).total_seconds()

        if time_since_open > edit_window:
            print(
                f"Edit received {time_since_open/60:.1f} min after open, "
                f"exceeds {edit_window/60:.1f} min window. Ignoring."
            )
            return

        # Re-parse the edited message
        new_signal = await self.parser.parse_signal(text)
        if new_signal is None:
            print("Edited message is no longer a trading signal, ignoring.")
            return

        # Compare and apply changes
        await self._apply_edit_changes(msg_id, dual, new_signal, text)

    async def _apply_edit_changes(
        self,
        msg_id: int,
        dual: DualPosition,
        new_signal: TradeSignal,
        edited_text: str,
    ) -> None:
        """Compare original signal with edited version and apply MT5 modifications.

        Args:
            msg_id: The Telegram message ID
            dual: The DualPosition containing tracked positions
            new_signal: The newly parsed signal from the edited message
            edited_text: The edited message text (for storing as original)
        """
        # Get reference position for original values
        ref_pos = dual.scalp or dual.runner
        if ref_pos is None:
            return

        original_sl = ref_pos.original_stop_loss or ref_pos.stop_loss
        original_tps = ref_pos.original_take_profits or ref_pos.take_profits

        # Detect what changed
        changes = []
        new_sl = new_signal.stop_loss
        new_tps = new_signal.take_profits

        sl_changed = new_sl and original_sl and abs(new_sl - original_sl) > 0.01
        tps_changed = new_tps != original_tps

        if sl_changed:
            changes.append(f"SL: {original_sl} -> {new_sl}")
        if tps_changed:
            changes.append(f"TPs: {original_tps} -> {new_tps}")

        if not changes:
            print("No significant changes detected in edit.")
            return

        print(f"Changes detected: {', '.join(changes)}")

        # Apply modifications to all open positions
        for pos in dual.all_positions:
            if pos.status == PositionStatus.CLOSED:
                continue

            # Determine appropriate TP for this position's role
            if pos.role == TradeRole.RUNNER and new_tps:
                new_tp = new_tps[-1]  # Runner targets last TP
            elif new_tps:
                new_tp = new_tps[0]  # Scalp targets TP1
            else:
                new_tp = None

            result = self.executor.modify_position(
                pos.mt5_ticket,
                sl=new_sl,
                tp=new_tp,
            )

            if result["success"]:
                # Update tracked position with new values
                if new_sl:
                    pos.stop_loss = new_sl
                if new_tps:
                    pos.take_profits = new_tps.copy()
                # Update original values to the corrected ones
                pos.original_message_text = edited_text
                pos.original_stop_loss = new_sl
                pos.original_take_profits = new_tps.copy() if new_tps else []
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Modified successfully")
            else:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Failed - {result.get('error', 'Unknown error')}")

        self.state.save()
        print("Edit changes applied and state saved.")

    def _resolve_target_msg_id(self, reply_to_msg_id: int | None) -> int | None:
        """Resolve the target message ID for position lookup.

        If reply_to_msg_id points to a tracked position, use it.
        Otherwise fall back to last_signal_msg_id (handles nested reply chains).

        This fixes the case where a TP1 hit message replies to a "40+ pips" message
        instead of the original signal - the reply chain is:
        TP1 hit -> 40+ pips -> original signal
        """
        if reply_to_msg_id is not None:
            # Check if this msg_id has a tracked position
            if self.state.get_dual_position_by_msg_id(reply_to_msg_id) is not None:
                return reply_to_msg_id
            # reply_to_msg_id exists but not tracked - likely a nested reply
            # Fall back to last signal
            print(f"  reply_to {reply_to_msg_id} not tracked, using last_signal_msg_id")
        return self.state.last_signal_msg_id

    async def _route_signal(
        self,
        msg_id: int,
        reply_to_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Route signal to the appropriate handler based on message type."""
        # Resolve target for position-related actions
        target_msg_id = self._resolve_target_msg_id(reply_to_msg_id)

        handlers = {
            MessageType.NEW_SIGNAL_COMPLETE: lambda: self._handle_new_signal(msg_id, signal, is_complete=True),
            MessageType.NEW_SIGNAL_INCOMPLETE: lambda: self._handle_new_signal(msg_id, signal, is_complete=False),
            MessageType.MODIFICATION: lambda: self._handle_modification(target_msg_id, signal),
            MessageType.RE_ENTRY: lambda: self._handle_re_entry(msg_id, target_msg_id, signal),
            MessageType.PROFIT_NOTIFICATION: lambda: self._handle_profit_notification(target_msg_id, signal),
            MessageType.CLOSE_SIGNAL: lambda: self._handle_close_signal(target_msg_id, signal),
            MessageType.PARTIAL_CLOSE: lambda: self._handle_partial_close(target_msg_id, signal),
            MessageType.COMPOUND_ACTION: lambda: self._handle_compound_action(msg_id, target_msg_id, signal),
        }

        handler = handlers.get(signal.message_type)
        if handler:
            await handler()

    async def _handle_new_signal(
        self,
        msg_id: int,
        signal: TradeSignal,
        is_complete: bool,
    ) -> None:
        """Handle new trading signal (complete or incomplete).

        Uses the configured strategy to determine how many trades to open.
        For dual_tp strategy: opens scalp (TP1) and runner (last TP) trades.
        For single strategy: opens one trade with TP1.
        """
        # Validate symbol
        if not self._config.symbols.is_allowed(signal.symbol):
            print(f"Symbol {signal.symbol} not in allowed list, skipping.")
            return

        broker_symbol = self._config.symbols.get_broker_symbol(signal.symbol)
        print(f"  Broker symbol: {broker_symbol}")

        # Check if there's a pending dual position for this symbol that needs completion
        pending_dual = self.state.get_pending_position_by_symbol(broker_symbol)
        if pending_dual and is_complete:
            print(f"  Found pending dual position for {broker_symbol}")
            print("  Completing pending positions instead of opening new trades...")
            await self._complete_pending_position(msg_id, pending_dual, signal)
            return

        # Calculate default SL if incomplete
        if not is_complete and signal.stop_loss is None:
            signal.stop_loss = self._calculate_default_sl(broker_symbol, signal)

        # Get trade configs from strategy
        trade_configs = self.strategy.get_trades_to_open(signal)
        if not trade_configs:
            print("  Strategy returned no trades to open")
            return

        print(f"  Strategy: opening {len(trade_configs)} trade(s)")

        # Execute trades using dual signal method
        results = self.executor.execute_dual_signal(
            signal,
            trade_configs,
            broker_symbol=broker_symbol,
            default_lot_size=self._config.trading.default_lot_size,
        )

        # Track each successful trade
        status = PositionStatus.OPEN if is_complete else PositionStatus.PENDING_COMPLETION
        now = datetime.now()
        any_success = False

        for trade_cfg in trade_configs:
            role_key = trade_cfg.role.value
            result = results.get(role_key)
            if not result or not result.get("success"):
                continue

            any_success = True
            self._log_trade_executed(result)

            # Determine TPs for this position
            if trade_cfg.role == TradeRole.SCALP or trade_cfg.role == TradeRole.SINGLE:
                pos_tps = [signal.take_profits[0]] if signal.take_profits else []
            else:  # RUNNER
                pos_tps = signal.take_profits  # Store all TPs for reference

            tracked = TrackedPosition(
                telegram_msg_id=msg_id,
                mt5_ticket=result["ticket"],
                symbol=result["symbol"],
                order_type=signal.order_type,
                entry_price=result["price"],
                stop_loss=signal.stop_loss,
                take_profits=pos_tps,
                lot_size=result["volume"],
                opened_at=now,
                is_complete=is_complete,
                status=status,
                tps_hit=[],
                role=trade_cfg.role,
                # Store original signal data for edit detection
                original_message_text=signal.comment,
                original_stop_loss=signal.stop_loss,
                original_take_profits=signal.take_profits.copy() if signal.take_profits else [],
            )
            self.state.add_position(tracked, trade_cfg.role)

        if any_success:
            self.state.save()

            # Start timeout if incomplete (for all positions)
            if not is_complete:
                # Use scalp ticket for timeout (any ticket works since they're linked)
                scalp_result = results.get("scalp") or results.get("single")
                if scalp_result and scalp_result.get("success"):
                    await self._start_timeout(msg_id, scalp_result["ticket"])
                    timeout_minutes = self._config.trading.incomplete_signal_timeout // 60
                    print(f"Started {timeout_minutes}-minutes timeout for incomplete signal")

            self._record_trade(signal, results)

    async def _complete_pending_position(
        self,
        new_msg_id: int,
        pending_dual: DualPosition,
        signal: TradeSignal,
    ) -> None:
        """Complete pending dual positions with SL/TP from new complete signal.

        Args:
            new_msg_id: The message ID of the complete signal (for future replies)
            pending_dual: The DualPosition containing pending positions
            signal: The complete signal with SL/TP values
        """
        old_msg_id = pending_dual.telegram_msg_id
        self._cancel_timeout(old_msg_id)

        new_sl = signal.stop_loss

        # Update each position in the dual
        any_success = False
        for pos in pending_dual.all_positions:
            if pos.status == PositionStatus.CLOSED:
                continue

            # Determine TP based on role
            if pos.role == TradeRole.RUNNER:
                new_tp = signal.take_profits[-1] if signal.take_profits else None
            else:  # SCALP or SINGLE
                new_tp = signal.take_profits[0] if signal.take_profits else None

            print(f"  Modifying {pos.role.value} position {pos.mt5_ticket}...")
            print(f"  New SL: {new_sl}, New TP: {new_tp}")

            # Verify position still exists on MT5
            mt5_pos = self.executor.get_position(pos.mt5_ticket)
            if mt5_pos is None:
                print(f"  WARNING: Position {pos.mt5_ticket} no longer exists on MT5!")
                pos.status = PositionStatus.CLOSED
                continue

            print(f"  Position verified on MT5: {mt5_pos['symbol']} @ {mt5_pos['price_open']}")

            # Validate SL/TP relative to actual entry price
            actual_entry = mt5_pos['price_open']
            is_buy = mt5_pos['type'] == 0  # MT5 type 0 = BUY
            validated_sl = new_sl
            validated_tp = new_tp

            # Validate TP
            if validated_tp is not None:
                if is_buy and validated_tp <= actual_entry:
                    print(f"  WARNING: Invalid TP {validated_tp} for BUY @ {actual_entry}")
                    validated_tp = None
                elif not is_buy and validated_tp >= actual_entry:
                    print(f"  WARNING: Invalid TP {validated_tp} for SELL @ {actual_entry}")
                    validated_tp = None

            # Validate SL
            if validated_sl is not None:
                if is_buy and validated_sl >= actual_entry:
                    print(f"  WARNING: Invalid SL {validated_sl} for BUY @ {actual_entry}")
                    validated_sl = None
                elif not is_buy and validated_sl <= actual_entry:
                    print(f"  WARNING: Invalid SL {validated_sl} for SELL @ {actual_entry}")
                    validated_sl = None

            if validated_sl is None and validated_tp is None:
                print(f"  ERROR: Both SL and TP invalid for {pos.role.value}")
                continue

            result = self.executor.modify_position(pos.mt5_ticket, sl=validated_sl, tp=validated_tp)

            if result["success"]:
                pos.stop_loss = validated_sl
                pos.take_profits = signal.take_profits if pos.role == TradeRole.RUNNER else [signal.take_profits[0]] if signal.take_profits else []
                pos.is_complete = True
                pos.status = PositionStatus.OPEN
                pos.telegram_msg_id = new_msg_id
                any_success = True
                print(f"  {pos.role.value.upper()} position {pos.mt5_ticket} completed!")
            else:
                print(f"  Failed to complete {pos.role.value}: {result['error']}")

        if any_success:
            # Reassign the dual position to the new message ID
            self.state.reassign_position(old_msg_id, new_msg_id)
            self.state.save()
            print(f"\nDual position reassigned: msg {old_msg_id} -> msg {new_msg_id}")

    def _get_best_tp(self, take_profits: list[float], order_type: OrderType) -> float | None:
        """Get TP1 (first take profit level) from the list.

        We only use TP1 because it's hit most frequently. TP2/TP3 are ignored.
        When TP1 is hit, the trade closes automatically on MT5.

        Args:
            take_profits: List of take profit prices (TP1, TP2, TP3...)
            order_type: The order direction (BUY/SELL) - unused but kept for API compatibility

        Returns:
            TP1 (first element), or None if no TPs
        """
        _ = order_type  # Unused - kept for API compatibility
        if not take_profits:
            return None

        # Always use TP1 (first element in the list)
        return take_profits[0]

    def _calculate_default_sl(self, broker_symbol: str, signal: TradeSignal) -> float | None:
        """Calculate default SL based on risk settings."""
        price = self.executor.get_current_price(
            broker_symbol,
            for_buy=signal.order_type == OrderType.BUY,
        )
        if price is None:
            return None

        sl = self.executor.calculate_default_sl(
            broker_symbol,
            signal.order_type,
            price,
            self._config.trading.default_lot_size,
            self._config.trading.max_risk_percent,
        )
        print(f"  Calculated risk-based SL: {sl:.5f}")
        return sl

    async def _handle_modification(
        self,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle modification message (update SL/TP) for all positions."""
        if target_msg_id is None:
            print("No target position found for modification")
            return

        dual = self.state.get_dual_position_by_msg_id(target_msg_id)
        if dual is None:
            print(f"Dual position for msg {target_msg_id} not found in state")
            return

        # Cancel timeout if position was pending
        self._cancel_timeout(target_msg_id)

        # Determine new SL value
        new_sl = signal.new_stop_loss or signal.stop_loss

        # Modify all positions in the dual
        for pos in dual.all_positions:
            if pos.status == PositionStatus.CLOSED:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket} is already closed")
                continue

            # Determine TP based on role
            if pos.role == TradeRole.RUNNER:
                new_tp = signal.take_profits[-1] if signal.take_profits else self._get_new_tp(signal, pos)
            else:
                new_tp = signal.take_profits[0] if signal.take_profits else self._get_new_tp(signal, pos)

            effective_sl = new_sl or pos.stop_loss
            result = self.executor.modify_position(pos.mt5_ticket, sl=effective_sl, tp=new_tp)

            if result["success"]:
                pos.stop_loss = effective_sl
                if signal.take_profits:
                    pos.take_profits = signal.take_profits if pos.role == TradeRole.RUNNER else [signal.take_profits[0]]
                pos.is_complete = True
                pos.status = PositionStatus.OPEN
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket} modified: SL={effective_sl}, TP={new_tp}")
            else:
                print(f"  {pos.role.value.upper()} modification failed: {result['error']}")

        self.state.save()

    def _get_new_tp(self, signal: TradeSignal, pos: TrackedPosition) -> float | None:
        """Get new TP value from signal or position."""
        if signal.new_take_profit:
            return signal.new_take_profit
        if signal.take_profits:
            return signal.take_profits[0]
        if pos.take_profits:
            return pos.take_profits[0]
        return None

    async def _handle_re_entry(
        self,
        new_msg_id: int,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle re-entry signal (close if in loss, open new)."""
        if target_msg_id is None:
            print("No target position found for re-entry")
            return

        pos = self.state.get_position_by_msg_id(target_msg_id)
        if pos is None:
            print(f"Position for msg {target_msg_id} not found in state")
            return

        if pos.status == PositionStatus.CLOSED:
            print(f"Position {pos.mt5_ticket} is already closed")
            return

        # Only re-enter if in loss
        if self.executor.is_position_profitable(pos.mt5_ticket):
            print(f"Position {pos.mt5_ticket} is in profit, ignoring re-entry")
            return

        print(f"Position {pos.mt5_ticket} is in loss, processing re-entry...")

        # Close the original position
        close_result = self.executor.close_position(pos.mt5_ticket)
        if not close_result["success"]:
            print(f"Failed to close original position: {close_result['error']}")
            return

        pos.status = PositionStatus.CLOSED
        self._cancel_timeout(target_msg_id)
        self.state.save()
        print(f"Closed original position at {close_result['closed_at']}")

        # Open new position with re-entry parameters
        re_entry_signal = TradeSignal(
            symbol=signal.symbol or pos.symbol,
            order_type=pos.order_type,  # Keep same direction
            entry_price=signal.re_entry_price,
            stop_loss=signal.new_stop_loss or signal.stop_loss,
            take_profits=pos.take_profits,  # Keep original TPs
            lot_size=signal.lot_size,
            comment=signal.comment,
            confidence=signal.confidence,
            message_type=MessageType.NEW_SIGNAL_COMPLETE,
            is_complete=True,
        )

        await self._handle_new_signal(new_msg_id, re_entry_signal, is_complete=True)

    async def _handle_profit_notification(
        self,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle profit notification using the strategy.

        Uses the strategy to determine:
        1. Whether to ignore the message (e.g., "book profits" without TP hit)
        2. What actions to take on TP hit (close scalp, move runner to breakeven)
        """
        print(f"Profit notification received (TP={signal.tp_hit_number})")

        # Check if strategy says to ignore this message
        if self.strategy.should_ignore_profit_message(signal):
            print("  Informational profit message (no TP hit) - ignoring per strategy")
            return

        if target_msg_id is None:
            print("No target position found")
            return

        dual = self.state.get_dual_position_by_msg_id(target_msg_id)
        if dual is None:
            print("Target dual position not found in state")
            return

        if dual.is_closed:
            print("All positions already closed")
            return

        # Get actions from strategy
        actions = self.strategy.on_tp_hit(signal.tp_hit_number, dual, signal)

        if not actions:
            print("  Strategy returned no actions")
            return

        # Execute each action
        for action in actions:
            pos = dual.get_by_role(action.role)
            if pos is None or pos.status == PositionStatus.CLOSED:
                continue

            if action.action_type == TradeActionType.VERIFY_CLOSED:
                # Check if position is closed on MT5
                mt5_pos = self.executor.get_position(pos.mt5_ticket)
                if mt5_pos is None:
                    print(f"  {action.role.value.upper()} {pos.mt5_ticket}: Confirmed closed on MT5")
                    pos.status = PositionStatus.CLOSED
                    if signal.tp_hit_number:
                        pos.tps_hit.append(signal.tp_hit_number)
                else:
                    print(f"  {action.role.value.upper()} {pos.mt5_ticket}: Still open, scheduling verification")
                    await self._start_tp_verification_timeout(target_msg_id, pos.mt5_ticket)

            elif action.action_type == TradeActionType.MOVE_SL_TO_BREAKEVEN:
                # Move SL to entry price (breakeven)
                mt5_pos = self.executor.get_position(pos.mt5_ticket)
                if mt5_pos is None:
                    print(f"  {action.role.value.upper()} {pos.mt5_ticket}: Already closed, skipping breakeven")
                    pos.status = PositionStatus.CLOSED
                else:
                    entry_price = action.value if action.value else pos.entry_price
                    result = self.executor.move_to_breakeven(pos.mt5_ticket, entry_price)
                    if result["success"]:
                        pos.stop_loss = entry_price
                        if signal.tp_hit_number:
                            pos.tps_hit.append(signal.tp_hit_number)
                        print(f"  {action.role.value.upper()}: SL moved to breakeven {entry_price}")
                    else:
                        print(f"  {action.role.value.upper()}: Failed to move SL: {result['error']}")

            elif action.action_type == TradeActionType.CLOSE:
                result = self.executor.close_position(pos.mt5_ticket)
                if result["success"]:
                    pos.status = PositionStatus.CLOSED
                    print(f"  {action.role.value.upper()} {pos.mt5_ticket}: Closed")
                else:
                    print(f"  {action.role.value.upper()}: Failed to close: {result['error']}")

        self.state.save()

    async def _handle_close_signal(
        self,
        target_msg_id: int | None,
        _signal: TradeSignal,
    ) -> None:
        """Handle close signal - closes ALL positions in the dual."""
        if target_msg_id is None:
            print("No target position found to close")
            return

        dual = self.state.get_dual_position_by_msg_id(target_msg_id)
        if dual is None:
            print(f"Dual position for msg {target_msg_id} not found")
            return

        if dual.is_closed:
            print("All positions already closed")
            return

        # Close all positions in the dual
        any_closed = False
        for pos in dual.all_positions:
            if pos.status == PositionStatus.CLOSED:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Already closed")
                continue

            result = self.executor.close_position(pos.mt5_ticket)
            if result["success"]:
                pos.status = PositionStatus.CLOSED
                any_closed = True
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Closed at {result['closed_at']}")
            else:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Failed to close: {result['error']}")

        if any_closed:
            self._cancel_timeout(target_msg_id)
            self.state.save()

    async def _handle_partial_close(
        self,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle partial close signal - applies to ALL positions in the dual."""
        print(f"Partial close signal received: {signal.close_percentage}%")

        if target_msg_id is None:
            print("No target position found for partial close")
            return

        if signal.close_percentage is None:
            print("No close percentage specified")
            return

        dual = self.state.get_dual_position_by_msg_id(target_msg_id)
        if dual is None:
            print(f"Dual position for msg {target_msg_id} not found")
            return

        if dual.is_closed:
            print("All positions already closed")
            return

        # Apply partial close to all positions in the dual
        any_success = False
        for pos in dual.all_positions:
            if pos.status == PositionStatus.CLOSED:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Already closed")
                continue

            result = self.executor.partial_close(pos.mt5_ticket, signal.close_percentage)
            if result["success"]:
                pos.lot_size = result["remaining_volume"]
                any_success = True
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Partial close successful")
                print(f"    Closed: {result['closed_volume']} lots @ {result['closed_at']}")
                print(f"    Remaining: {result['remaining_volume']} lots")
            else:
                print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Failed: {result['error']}")

        if any_success:
            self.state.save()

    async def _handle_compound_action(
        self,
        msg_id: int,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle compound action containing multiple operations.

        A compound action can contain both a new pending order AND a modification
        to an existing position. For example:
        - "Add Sell-Limit 4342-4343, TP 4334, TP 4320, Update SL to 4344.5"

        This processes modifications first (to protect the losing position),
        then places new pending orders.
        """
        if not signal.actions:
            print("Compound action has no actions to process")
            return

        print(f"\nProcessing compound action with {len(signal.actions)} actions...")

        # Get the original position if this is a reply
        original_pos = None
        if target_msg_id:
            original_pos = self.state.get_position_by_msg_id(target_msg_id)
            if original_pos:
                print(f"  Target position: {original_pos.mt5_ticket} ({original_pos.symbol})")

        # Separate actions by type
        modification_actions = [a for a in signal.actions if a.get("action_type") == "modification"]
        new_signal_actions = [a for a in signal.actions if a.get("action_type") == "new_signal"]

        # Step 1: Apply modifications FIRST (protects the losing position)
        modification_sl = None
        for action in modification_actions:
            new_sl = action.get("new_stop_loss")
            new_tp = action.get("new_take_profit")

            if original_pos and original_pos.status != PositionStatus.CLOSED:
                print(f"  Applying modification: SL={new_sl}, TP={new_tp}")
                result = self.executor.modify_position(
                    original_pos.mt5_ticket, sl=new_sl, tp=new_tp
                )
                if result["success"]:
                    if new_sl:
                        original_pos.stop_loss = new_sl
                        modification_sl = new_sl  # Save for pending order inheritance
                    self.state.save()
                    print(f"  Modified position {original_pos.mt5_ticket}")
                else:
                    print(f"  Modification failed: {result['error']}")
            else:
                # No original position, just save the SL for pending order
                modification_sl = new_sl
                print(f"  No position to modify, will use SL {new_sl} for pending order")

        # Step 2: Place new pending orders SECOND
        for action in new_signal_actions:
            order_type_str = action.get("order_type")
            if not order_type_str:
                print("  Skipping action with no order_type")
                continue

            try:
                order_type = OrderType(order_type_str)
            except ValueError:
                print(f"  Invalid order_type: {order_type_str}")
                continue

            # Determine symbol (from action, signal, or original position)
            symbol = signal.symbol
            if not symbol and original_pos:
                symbol = original_pos.symbol

            if not symbol:
                print("  Cannot determine symbol for pending order")
                continue

            # Validate symbol
            if not self._config.symbols.is_allowed(symbol):
                print(f"  Symbol {symbol} not in allowed list, skipping")
                continue

            broker_symbol = self._config.symbols.get_broker_symbol(symbol)

            # Determine SL: action's SL > modification SL > calculate default
            pending_sl = action.get("stop_loss") or modification_sl
            if pending_sl is None:
                # Calculate default SL for pending order
                entry_price = action.get("entry_price")
                if entry_price:
                    pending_sl = self.executor.calculate_default_sl(
                        broker_symbol,
                        order_type,
                        entry_price,
                        self._config.trading.default_lot_size,
                        self._config.trading.max_risk_percent,
                    )
                    print(f"  Calculated default SL for pending order: {pending_sl}")

            # Build pending order signal
            pending_signal = TradeSignal(
                symbol=symbol,
                order_type=order_type,
                entry_price=action.get("entry_price"),
                stop_loss=pending_sl,
                take_profits=action.get("take_profits", []),
                message_type=MessageType.NEW_SIGNAL_COMPLETE,
                is_complete=pending_sl is not None and len(action.get("take_profits", [])) > 0,
            )

            print(f"  Placing pending order: {order_type.value} @ {pending_signal.entry_price}")
            print(f"    SL: {pending_sl}, TPs: {pending_signal.take_profits}")

            # Execute the pending order
            await self._handle_new_signal(msg_id, pending_signal, is_complete=pending_signal.is_complete)

    async def _start_timeout(self, msg_id: int, ticket: int) -> None:
        """Start timeout for incomplete signal - closes ALL positions in the dual."""
        _ = ticket  # Kept for API compatibility
        timeout_seconds = self._config.trading.incomplete_signal_timeout

        async def timeout_handler() -> None:
            await asyncio.sleep(timeout_seconds)
            dual = self.state.get_dual_position_by_msg_id(msg_id)
            if dual is None:
                self._pending_timeouts.pop(msg_id, None)
                return

            # Check if any position is still pending
            pending_positions = [
                pos for pos in dual.all_positions
                if pos.status == PositionStatus.PENDING_COMPLETION
            ]

            if not pending_positions:
                self._pending_timeouts.pop(msg_id, None)
                return

            print(f"\nTimeout expired for incomplete signal {msg_id}")
            print(f"Closing {len(pending_positions)} pending position(s)...")

            for pos in pending_positions:
                result = self.executor.close_position(pos.mt5_ticket)
                if result["success"]:
                    pos.status = PositionStatus.CLOSED
                    print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Closed due to timeout")
                else:
                    print(f"  {pos.role.value.upper()} {pos.mt5_ticket}: Failed to close: {result['error']}")

            self.state.save()
            self._pending_timeouts.pop(msg_id, None)

        task = asyncio.create_task(timeout_handler())
        self._pending_timeouts[msg_id] = task

    def _cancel_timeout(self, msg_id: int) -> None:
        """Cancel pending timeout for a message."""
        task = self._pending_timeouts.pop(msg_id, None)
        if task:
            task.cancel()
            print(f"Cancelled timeout for msg {msg_id}")

    async def _start_tp_verification_timeout(self, msg_id: int, ticket: int) -> None:
        """Start 5-minute verification timeout after TP hit notification.

        If position is still open after 5 minutes, close it manually.
        This handles cases where MT5 TP was not triggered but signal says TP hit.
        """
        # Use the same timeout as incomplete signals (5 minutes)
        timeout_seconds = self._config.trading.incomplete_signal_timeout
        # Use ticket as unique key to allow multiple verifications per msg_id
        timeout_key = (msg_id, ticket)

        async def verification_handler() -> None:
            await asyncio.sleep(timeout_seconds)
            # Find the position by ticket (handles dual positions correctly)
            result = self.state.get_position_by_ticket(ticket)
            if result is None:
                print(f"\nTP verification: Position {ticket} not found")
                self._tp_verification_timeouts.pop(timeout_key, None)
                return

            pos, role = result
            if pos.status == PositionStatus.CLOSED:
                print(f"\nTP verification: {role.value.upper()} {ticket} already closed")
                self._tp_verification_timeouts.pop(timeout_key, None)
                return

            # Check MT5 again
            mt5_pos = self.executor.get_position(ticket)
            if mt5_pos is None:
                # Position closed on MT5
                print(f"\nTP verification: {role.value.upper()} {ticket} confirmed closed on MT5")
                pos.status = PositionStatus.CLOSED
                self.state.save()
            else:
                # Position still open - force close
                print(f"\nTP verification: {role.value.upper()} {ticket} still open after 5 min, force closing...")
                close_result = self.executor.close_position(ticket)
                if close_result["success"]:
                    pos.status = PositionStatus.CLOSED
                    self.state.save()
                    print(f"  Force closed at {close_result['closed_at']}")
                else:
                    print(f"  Failed to force close: {close_result['error']}")

            self._tp_verification_timeouts.pop(timeout_key, None)

        # Cancel any existing verification timeout for this ticket
        existing_task = self._tp_verification_timeouts.pop(timeout_key, None)
        if existing_task:
            existing_task.cancel()

        task = asyncio.create_task(verification_handler())
        self._tp_verification_timeouts[timeout_key] = task
        print(f"  Started 5-minute verification timeout for position {ticket}")

    def _log_message_received(self, msg_id: int, reply_to: int | None, text: str) -> None:
        """Log received message details."""
        print(f"\n{'=' * 50}")
        print(f"Message ID: {msg_id}")
        if reply_to:
            print(f"Reply to: {reply_to}")
        print(f"Text: {text[:100]}...")

    def _log_signal_parsed(self, signal: TradeSignal) -> None:
        """Log parsed signal details."""
        print(f"\nClassified as: {signal.message_type.value}")
        print(f"  Symbol: {signal.symbol}")
        print(f"  Confidence: {signal.confidence:.0%}")

    def _log_trade_executed(self, result: dict) -> None:
        """Log executed trade details."""
        print("\nTrade executed successfully!")
        print(f"  Ticket: {result['ticket']}")
        print(f"  Volume: {result['volume']}")
        print(f"  Price: {result['price']}")

    def _record_trade(self, signal: TradeSignal, result: dict) -> None:
        """Record trade in history log."""
        self.trade_log.append({
            "time": datetime.now().isoformat(),
            "signal": signal.comment,
            "result": result,
        })

    def stop(self) -> None:
        """Stop the bot and cleanup resources."""
        self._shutdown_requested = True

        # Cancel all pending timeouts
        for task in self._pending_timeouts.values():
            task.cancel()
        self._pending_timeouts.clear()

        # Cancel all TP verification timeouts
        for task in self._tp_verification_timeouts.values():
            task.cancel()
        self._tp_verification_timeouts.clear()

        # Disconnect Telegram
        if self._telegram.is_connected():
            self._telegram.disconnect()

        self.state.save()
        self.executor.disconnect()
        print("Bot stopped.")


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
