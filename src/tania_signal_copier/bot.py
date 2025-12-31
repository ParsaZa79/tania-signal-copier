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

    async def start(self) -> None:
        """Start the bot and begin monitoring the Telegram channel."""
        print("Starting Telegram MT5 Signal Bot...")

        # Load saved state
        self.state.load()
        print(f"Loaded {len(self.state)} tracked positions from state")

        # Connect to MT5
        if not self.executor.connect():
            print("Failed to connect to MT5. Exiting.")
            return

        # Connect to Telegram
        await self._telegram.start()  # type: ignore[misc]
        print("Connected to Telegram")

        # Get the channel entity
        try:
            channel = await self._telegram.get_entity(self._config.telegram.channel)
            channel_name = getattr(channel, "title", self._config.telegram.channel)
            print(f"Monitoring channel: {channel_name}")
        except Exception as e:
            print(f"Could not find channel: {e}")
            return

        # Register message handler
        @self._telegram.on(events.NewMessage(chats=channel))
        async def handle_new_message(event: events.NewMessage.Event) -> None:
            await self._process_message(event)

        print("Bot is running! Waiting for signals...")
        await self._telegram.run_until_disconnected()  # type: ignore[misc]

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
        """Get the least profitable (closest) TP based on order direction.

        For SELL: highest TP (closest to entry = less profit)
        For BUY: lowest TP (closest to entry = less profit)

        Args:
            take_profits: List of take profit prices
            order_type: The order direction (BUY/SELL)

        Returns:
            The least profitable TP, or None if no TPs
        """
        if not take_profits:
            return None

        is_sell = order_type in [OrderType.SELL, OrderType.SELL_LIMIT, OrderType.SELL_STOP]
        return max(take_profits) if is_sell else min(take_profits)

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
        """Handle TP hit / profit notification."""
        print("Profit notification received")

        if not signal.move_sl_to_entry:
            print("No action required (move_sl_to_entry not specified)")
            return

        if target_msg_id is None:
            print("No target position found")
            return

        pos = self.state.get_position_by_msg_id(target_msg_id)
        if pos is None or pos.status == PositionStatus.CLOSED:
            print("Target position not found or closed")
            return

        # Move SL to entry
        result = self.executor.modify_position(pos.mt5_ticket, sl=pos.entry_price)
        if result["success"]:
            pos.stop_loss = pos.entry_price
            self.state.save()
            print(f"Moved SL to entry ({pos.entry_price}) for position {pos.mt5_ticket}")
        else:
            print(f"Failed to move SL to entry: {result['error']}")

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
        # Cancel all pending timeouts
        for task in self._pending_timeouts.values():
            task.cancel()
        self._pending_timeouts.clear()

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
