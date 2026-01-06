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
from datetime import datetime

from telethon import TelegramClient, events

from tania_signal_copier.config import BotConfig, config
from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.models import (
    MessageType,
    OrderType,
    PositionStatus,
    TrackedPosition,
    TradeSignal,
)
from tania_signal_copier.parser import SignalParser
from tania_signal_copier.state import BotState


class TelegramMT5Bot:
    """Main bot that connects Telegram signals to MT5.

    This class coordinates all components:
    - Telegram client for receiving messages
    - SignalParser for AI-powered message classification
    - MT5Executor for trade execution
    - BotState for position tracking

    Attributes:
        parser: The signal parser instance
        executor: The MT5 executor instance
        state: The persistent state manager
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

        self._telegram = TelegramClient(
            self._config.telegram.session_name,
            self._config.telegram.api_id,
            self._config.telegram.api_hash,
        )

        # Timeout management
        self._pending_timeouts: dict[int, asyncio.Task] = {}

        # Trade log for history
        self.trade_log: list[dict] = []

        # Reconnection settings
        self._max_reconnect_attempts = 0  # 0 = infinite
        self._reconnect_delay = 10  # seconds between attempts
        self._max_reconnect_delay = 300  # max 5 minutes
        self._shutdown_requested = False
        self._handle_telegram_event: events.NewMessage | None = None

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

                # Register message handler (remove old handlers first to avoid duplicates)
                if self._handle_telegram_event is not None:
                    self._telegram.remove_event_handler(self._handle_telegram_event)

                @self._telegram.on(events.NewMessage(chats=channel))
                async def handle_new_message(event: events.NewMessage.Event) -> None:
                    await self._process_message(event)

                # Store reference for cleanup
                self._handle_telegram_event = handle_new_message

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

    async def _route_signal(
        self,
        msg_id: int,
        reply_to_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Route signal to the appropriate handler based on message type."""
        handlers = {
            MessageType.NEW_SIGNAL_COMPLETE: lambda: self._handle_new_signal(msg_id, signal, is_complete=True),
            MessageType.NEW_SIGNAL_INCOMPLETE: lambda: self._handle_new_signal(msg_id, signal, is_complete=False),
            MessageType.MODIFICATION: lambda: self._handle_modification(
                reply_to_msg_id or self.state.last_signal_msg_id, signal
            ),
            MessageType.RE_ENTRY: lambda: self._handle_re_entry(
                msg_id, reply_to_msg_id or self.state.last_signal_msg_id, signal
            ),
            MessageType.PROFIT_NOTIFICATION: lambda: self._handle_profit_notification(
                reply_to_msg_id or self.state.last_signal_msg_id, signal
            ),
            MessageType.CLOSE_SIGNAL: lambda: self._handle_close_signal(
                reply_to_msg_id or self.state.last_signal_msg_id, signal
            ),
            MessageType.COMPOUND_ACTION: lambda: self._handle_compound_action(
                msg_id, reply_to_msg_id or self.state.last_signal_msg_id, signal
            ),
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
        """Handle new trading signal (complete or incomplete)."""
        # Validate symbol
        if not self._config.symbols.is_allowed(signal.symbol):
            print(f"Symbol {signal.symbol} not in allowed list, skipping.")
            return

        broker_symbol = self._config.symbols.get_broker_symbol(signal.symbol)
        print(f"  Broker symbol: {broker_symbol}")

        # Check if there's a pending position for this symbol that needs completion
        pending_pos = self.state.get_pending_position_by_symbol(broker_symbol)
        if pending_pos and is_complete:
            print(f"  Found pending position {pending_pos.mt5_ticket} for {broker_symbol}")
            print("  Completing pending position instead of opening new trade...")
            await self._complete_pending_position(msg_id, pending_pos, signal)
            return

        # Calculate default SL if incomplete
        if not is_complete and signal.stop_loss is None:
            signal.stop_loss = self._calculate_default_sl(broker_symbol, signal)

        # Execute the trade
        result = self.executor.execute_signal(
            signal,
            broker_symbol=broker_symbol,
            default_lot_size=self._config.trading.default_lot_size,
        )

        if not result["success"]:
            print(f"\nTrade failed: {result['error']}")
            return

        self._log_trade_executed(result)

        # Track position
        status = PositionStatus.OPEN if is_complete else PositionStatus.PENDING_COMPLETION
        tracked = TrackedPosition(
            telegram_msg_id=msg_id,
            mt5_ticket=result["ticket"],
            symbol=result["symbol"],
            order_type=signal.order_type,
            entry_price=result["price"],
            stop_loss=signal.stop_loss,
            take_profits=signal.take_profits,
            lot_size=result["volume"],
            opened_at=datetime.now(),
            is_complete=is_complete,
            status=status,
            tps_hit=[],
        )
        self.state.add_position(tracked)
        self.state.save()

        # Start timeout if incomplete
        if not is_complete:
            await self._start_timeout(msg_id, result["ticket"])
            print("Started 2-minute timeout for incomplete signal")

        self._record_trade(signal, result)

    async def _complete_pending_position(
        self,
        new_msg_id: int,
        pending_pos: TrackedPosition,
        signal: TradeSignal,
    ) -> None:
        """Complete a pending position with SL/TP from new complete signal.

        Args:
            new_msg_id: The message ID of the complete signal (for future replies)
            pending_pos: The pending position to complete
            signal: The complete signal with SL/TP values
        """
        # Cancel the timeout
        old_msg_id = pending_pos.telegram_msg_id
        self._cancel_timeout(old_msg_id)

        # Determine new SL/TP values
        new_sl = signal.stop_loss or pending_pos.stop_loss
        # Use the most profitable TP: lowest for SELL, highest for BUY
        new_tp = self._get_best_tp(signal.take_profits, pending_pos.order_type)

        print(f"  Modifying position {pending_pos.mt5_ticket}...")
        print(f"  New SL: {new_sl}, New TP: {new_tp}")

        # Verify position still exists on MT5
        mt5_pos = self.executor.get_position(pending_pos.mt5_ticket)
        if mt5_pos is None:
            print(f"\nWARNING: Position {pending_pos.mt5_ticket} no longer exists on MT5!")
            print("  The position may have been closed (SL hit or manual close)")
            pending_pos.status = PositionStatus.CLOSED
            self.state.save()
            return

        print(f"  Position verified on MT5: {mt5_pos['symbol']} @ {mt5_pos['price_open']}")

        # Validate SL/TP relative to actual entry price
        actual_entry = mt5_pos['price_open']
        is_buy = mt5_pos['type'] == 0  # MT5 type 0 = BUY

        # Validate and fix TP if it's on the wrong side of entry
        if new_tp is not None:
            if is_buy and new_tp <= actual_entry:
                print(f"\nWARNING: Invalid TP {new_tp} for BUY @ {actual_entry} (TP must be above entry)")
                print("  Signal prices may be stale or corrupted - skipping TP update")
                new_tp = None  # Don't set invalid TP
            elif not is_buy and new_tp >= actual_entry:
                print(f"\nWARNING: Invalid TP {new_tp} for SELL @ {actual_entry} (TP must be below entry)")
                print("  Signal prices may be stale or corrupted - skipping TP update")
                new_tp = None

        # Validate and fix SL if it's on the wrong side of entry
        if new_sl is not None:
            if is_buy and new_sl >= actual_entry:
                print(f"\nWARNING: Invalid SL {new_sl} for BUY @ {actual_entry} (SL must be below entry)")
                print("  Signal prices may be stale or corrupted - skipping SL update")
                new_sl = None
            elif not is_buy and new_sl <= actual_entry:
                print(f"\nWARNING: Invalid SL {new_sl} for SELL @ {actual_entry} (SL must be above entry)")
                print("  Signal prices may be stale or corrupted - skipping SL update")
                new_sl = None

        # If both SL and TP are invalid, we can't complete the position properly
        if new_sl is None and new_tp is None:
            print("\nERROR: Both SL and TP are invalid - cannot complete position")
            print("  Keeping existing position SL/TP unchanged")
            return

        result = self.executor.modify_position(pending_pos.mt5_ticket, sl=new_sl, tp=new_tp)

        if result["success"]:
            pending_pos.stop_loss = new_sl
            pending_pos.take_profits = signal.take_profits
            pending_pos.is_complete = True
            pending_pos.status = PositionStatus.OPEN

            # Update the message ID so replies to the complete signal can find this position
            pending_pos.telegram_msg_id = new_msg_id
            self.state.remove_position(old_msg_id)
            self.state.add_position(pending_pos)
            self.state.save()

            print(f"\nPosition {pending_pos.mt5_ticket} completed successfully!")
            print(f"  SL: {new_sl}")
            print(f"  TP: {new_tp}")
            print(f"  TPs: {signal.take_profits}")
            print(f"  Updated tracking: msg {old_msg_id} -> msg {new_msg_id}")
        else:
            print(f"\nFailed to complete position: {result['error']}")
            print(f"  Full result: {result}")

    def _get_best_tp(self, take_profits: list[float], order_type: OrderType) -> float | None:
        """Get the furthest (most profitable) TP based on order direction.

        Sets the final TP on MT5 so that intermediate TPs can trigger
        profit notifications for progressive SL movement.

        For BUY: highest TP (furthest from entry = most profit)
        For SELL: lowest TP (furthest from entry = most profit)

        Args:
            take_profits: List of take profit prices
            order_type: The order direction (BUY/SELL)

        Returns:
            The most profitable TP, or None if no TPs
        """
        if not take_profits:
            return None

        is_sell = order_type in [OrderType.SELL, OrderType.SELL_LIMIT, OrderType.SELL_STOP]
        return min(take_profits) if is_sell else max(take_profits)

    def _determine_tp_hit(
        self,
        signal: TradeSignal,
        pos: TrackedPosition,
    ) -> int | None:
        """Determine which TP number was hit from signal and position context.

        Args:
            signal: The parsed profit notification signal
            pos: The tracked position

        Returns:
            TP number (1, 2, 3, etc.) or None if cannot be determined.
            Returns None for informational messages that don't confirm a TP hit.
        """
        # Only act if parser explicitly detected a TP hit number
        if signal.tp_hit_number is not None:
            return signal.tp_hit_number

        # Only act if parser explicitly detected instruction to move SL to entry
        # (e.g., "move SL to entry", "breakeven", NOT "book profits")
        if signal.move_sl_to_entry:
            # If we already have TPs hit, move to next level
            if pos.tps_hit:
                return max(pos.tps_hit) + 1
            else:
                return 1  # Assume TP1 if explicit move_sl_to_entry instruction

        # If neither tp_hit_number nor move_sl_to_entry is set,
        # this is just an informational message - don't move SL
        return None

    def _calculate_progressive_sl(
        self,
        tp_number: int,
        pos: TrackedPosition,
    ) -> float | None:
        """Calculate new SL level based on which TP was hit.

        Progressive SL rules:
        - TP1 hit -> SL moves to Entry
        - TP2 hit -> SL moves to TP1
        - TP3 hit -> SL moves to TP2
        - etc.

        Args:
            tp_number: Which TP was hit (1, 2, 3, etc.)
            pos: The tracked position with entry and TP levels

        Returns:
            New SL price or None if cannot calculate
        """
        if tp_number == 1:
            # TP1 hit -> move to entry
            return pos.entry_price

        # For TP2+, move to the previous TP level
        # TPs are stored as a list - need to get the correct one
        previous_tp_index = tp_number - 2  # TP2 -> index 0 (TP1), TP3 -> index 1 (TP2)

        if not pos.take_profits:
            print(f"No take_profits stored for position {pos.mt5_ticket}")
            return pos.entry_price  # Fallback to entry

        # Sort TPs correctly based on order direction
        is_buy = pos.order_type in [OrderType.BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]
        sorted_tps = sorted(pos.take_profits, reverse=not is_buy)
        # For BUY: ascending (TP1 < TP2 < TP3)
        # For SELL: descending (TP1 > TP2 > TP3)

        if previous_tp_index < 0 or previous_tp_index >= len(sorted_tps):
            print(f"TP{tp_number - 1} not found in position (only {len(sorted_tps)} TPs)")
            return pos.entry_price  # Fallback to entry if TP not found

        return sorted_tps[previous_tp_index]

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
        """Handle modification message (update SL/TP)."""
        if target_msg_id is None:
            print("No target position found for modification")
            return

        pos = self.state.get_position_by_msg_id(target_msg_id)
        if pos is None:
            print(f"Position for msg {target_msg_id} not found in state")
            return

        if pos.status == PositionStatus.CLOSED:
            print(f"Position {pos.mt5_ticket} is already closed")
            return

        # Cancel timeout if position was pending
        self._cancel_timeout(target_msg_id)

        # Determine new SL/TP values
        new_sl = signal.new_stop_loss or signal.stop_loss or pos.stop_loss
        new_tp = self._get_new_tp(signal, pos)

        result = self.executor.modify_position(pos.mt5_ticket, sl=new_sl, tp=new_tp)

        if result["success"]:
            pos.stop_loss = new_sl
            if signal.take_profits:
                pos.take_profits = signal.take_profits
            pos.is_complete = True
            pos.status = PositionStatus.OPEN
            self.state.save()
            print(f"Position {pos.mt5_ticket} modified: SL={new_sl}, TP={new_tp}")
        else:
            print(f"Modification failed: {result['error']}")

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
        """Handle TP hit / profit notification with progressive SL movement.

        Progressive SL rules:
        - TP1 hit -> SL moves to Entry
        - TP2 hit -> SL moves to TP1
        - TP3 hit -> SL moves to TP2
        - etc.
        """
        print("Profit notification received")

        if target_msg_id is None:
            print("No target position found")
            return

        pos = self.state.get_position_by_msg_id(target_msg_id)
        if pos is None or pos.status == PositionStatus.CLOSED:
            print("Target position not found or closed")
            return

        # Determine which TP was hit
        tp_number = self._determine_tp_hit(signal, pos)
        if tp_number is None:
            print("Could not determine which TP was hit, no action taken")
            return

        print(f"  TP{tp_number} hit detected")

        # Check if this TP was already processed
        if tp_number in pos.tps_hit:
            print(f"  TP{tp_number} already processed, skipping")
            return

        # Calculate new SL based on TP hit
        new_sl = self._calculate_progressive_sl(tp_number, pos)
        if new_sl is None:
            print(f"  Could not calculate new SL for TP{tp_number}")
            return

        # Only modify if new SL is better (more protective)
        current_sl = pos.stop_loss
        if current_sl is not None:
            is_buy = pos.order_type in [OrderType.BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]
            if is_buy and new_sl <= current_sl:
                print(f"  New SL {new_sl} is not better than current {current_sl} for BUY, skipping")
                return
            if not is_buy and new_sl >= current_sl:
                print(f"  New SL {new_sl} is not better than current {current_sl} for SELL, skipping")
                return

        # Move SL
        result = self.executor.modify_position(pos.mt5_ticket, sl=new_sl)
        if result["success"]:
            pos.stop_loss = new_sl
            pos.tps_hit.append(tp_number)
            self.state.save()
            print(f"  TP{tp_number} hit: Moved SL to {new_sl} for position {pos.mt5_ticket}")
        else:
            print(f"  Failed to move SL: {result['error']}")

    async def _handle_close_signal(
        self,
        target_msg_id: int | None,
        signal: TradeSignal,
    ) -> None:
        """Handle close signal."""
        if target_msg_id is None:
            print("No target position found to close")
            return

        pos = self.state.get_position_by_msg_id(target_msg_id)
        if pos is None:
            print(f"Position for msg {target_msg_id} not found")
            return

        if pos.status == PositionStatus.CLOSED:
            print(f"Position {pos.mt5_ticket} is already closed")
            return

        result = self.executor.close_position(pos.mt5_ticket)
        if result["success"]:
            pos.status = PositionStatus.CLOSED
            self._cancel_timeout(target_msg_id)
            self.state.save()
            print(f"Position {pos.mt5_ticket} closed at {result['closed_at']}")
        else:
            print(f"Failed to close position: {result['error']}")

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
        """Start timeout for incomplete signal."""
        timeout_seconds = self._config.trading.incomplete_signal_timeout

        async def timeout_handler() -> None:
            await asyncio.sleep(timeout_seconds)
            pos = self.state.get_position_by_msg_id(msg_id)
            if pos and pos.status == PositionStatus.PENDING_COMPLETION:
                print(f"\nTimeout expired for incomplete signal {msg_id}")
                print(f"Closing position {ticket}...")
                result = self.executor.close_position(ticket)
                if result["success"]:
                    pos.status = PositionStatus.CLOSED
                    self.state.save()
                    print("Position closed due to timeout")
                else:
                    print(f"Failed to close: {result['error']}")
            self._pending_timeouts.pop(msg_id, None)

        task = asyncio.create_task(timeout_handler())
        self._pending_timeouts[msg_id] = task

    def _cancel_timeout(self, msg_id: int) -> None:
        """Cancel pending timeout for a message."""
        task = self._pending_timeouts.pop(msg_id, None)
        if task:
            task.cancel()
            print(f"Cancelled timeout for msg {msg_id}")

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
