"""
Signal parser for the Telegram MT5 Signal Bot.

This module uses Groq AI to parse and classify trading signals
from Telegram messages into structured TradeSignal objects.
"""

import json
import re

from groq import AsyncGroq

from tania_signal_copier.models import ActionType, MessageType, OrderType, ParsedAction, TradeSignal


class SignalParser:
    """Uses Groq AI to parse trading signals from various formats.

    This parser classifies incoming Telegram messages into 8 types
    and extracts structured trading information.

    Message Types:
        - NEW_SIGNAL_COMPLETE: Full signal with SL, TP, Entry
        - NEW_SIGNAL_INCOMPLETE: Missing SL/TP/Entry
        - MODIFICATION: Update SL/TP request
        - RE_ENTRY: New entry for same symbol
        - PROFIT_NOTIFICATION: TP hit, profit info
        - CLOSE_SIGNAL: Close position request
        - COMPOUND_ACTION: Multiple actions (new order + modification)
        - NOT_TRADING: Non-trading content
    """

    SYSTEM_PROMPT = """Analyze this forex/gold trading message and extract ALL actions.

IMPORTANT: A message can contain MULTIPLE independent actions. Always return ALL actions in the "actions" array.

ACTION TYPES:
1. "new_signal" - Open new position/pending order (contains symbol + direction + usually entry/SL/TPs)
2. "modification" - Change SL/TP to specific price (e.g., "move SL to 2650", "new SL 2640")
3. "move_sl_to_entry" - Move SL to breakeven/entry (e.g., "SL to entry", "secure at breakeven")
4. "partial_close" - Close X% of position (e.g., "close half", "close 70%")
5. "full_close" - Close entire position (e.g., "close gold", "exit trade")
6. "tp_hit" - TP was hit notification (e.g., "TP1 hit", "first target reached")
7. "re_entry" - Close losing position and re-enter (contains "re-entry" + new entry/SL)

MULTI-ACTION EXAMPLES:
- "CLOSE HALF FOR 54+ PIPS, MOVE SL TO ENTRY" → 2 actions: partial_close + move_sl_to_entry
- "TP1 HIT, MOVE SL TO BREAKEVEN" → 2 actions: tp_hit + move_sl_to_entry
- "Add Sell-Limit 4342, Update SL to 4344" → 2 actions: new_signal + modification

ORDER TYPE RULES (for new_signal actions):
- "buy" or "sell" = MARKET orders (execute immediately). Use for "BUY GOLD @", "SELL XAUUSD @".
- "buy_limit", "sell_limit", "buy_stop", "sell_stop" = PENDING orders. ONLY if message says "limit" or "stop".

MOVE_SL_TO_ENTRY vs MODIFICATION:
- Use "move_sl_to_entry" for: "SL to entry", "SL to breakeven", "secure at entry", "move SL to entry"
- Use "modification" with new_stop_loss for: "move SL to 2650", "SL 2640", "new SL 2635" (specific price)

TP_HIT RULES:
- ONLY use tp_hit if message EXPLICITLY confirms TP was hit: "TP1 hit", "First target reached", "TP2 ✅"
- Messages like "+50 pips running", "book some profits" are NOT tp_hit - they're informational

Return JSON:
{{
    "symbol": "XAUUSD" or null,
    "actions": [
        {{
            "action_type": "new_signal|modification|move_sl_to_entry|partial_close|full_close|tp_hit|re_entry",
            "order_type": "buy|sell|buy_limit|sell_limit|buy_stop|sell_stop" or null,
            "entry_price": number or null,
            "entry_price_max": number or null,
            "stop_loss": number or null,
            "take_profits": [numbers] or [],
            "new_stop_loss": number or null,
            "new_take_profit": number or null,
            "close_percentage": number or null (for partial_close, e.g., 50 for "close half"),
            "tp_hit_number": 1|2|3|null (for tp_hit),
            "re_entry_price": number or null,
            "re_entry_price_max": number or null
        }}
    ],
    "confidence": 0-1
}}

IMPORTANT:
- ALWAYS populate "actions" array, even for single actions
- For non-trading messages (ads, greetings), return empty actions array: {{"symbol": null, "actions": [], "confidence": 1.0}}

Return ONLY valid JSON, no explanation."""

    CORRECTION_SYSTEM_PROMPT = """You are analyzing a CORRECTION message for a trading signal.

The original signal had these values:
- Entry Price: {original_entry}
- Stop Loss: {original_sl}
- Take Profits: {original_tps}
- Symbol: {symbol}
- Order Type: {order_type}

Common shorthand correction patterns traders use:
- "44*" or "*44" = The significant digits should be 44xx (e.g., 4146 was typo, meant 4446)
- "SL 2640" or "sl:2640" = New stop loss is 2640
- "TP 2700" or "tp:2700" = New take profit is 2700
- Just a number like "4446" = Usually correcting the most recently mentioned or most likely wrong value
- "44" (two digits) = Replace the significant digits in the wrong value

Analyze the correction and determine what value(s) the trader meant to fix.
Consider which original value the correction most likely refers to based on digit patterns.

Return JSON:
{{
    "corrected_entry": number or null,
    "corrected_stop_loss": number or null,
    "corrected_take_profits": [numbers] or null,
    "confidence": 0-1,
    "interpretation": "brief explanation of what was corrected and why"
}}

Return ONLY valid JSON, no explanation outside the JSON."""

    def __init__(self) -> None:
        """Initialize parser with Groq async client."""
        self.client = AsyncGroq()  # Reads GROQ_API_KEY from environment

    def _strip_markdown(self, text: str) -> str:
        """Strip Telegram markdown formatting from text.

        Removes bold (**), italic (__), strikethrough (~~), and code (`) markers
        that can corrupt number parsing.

        Args:
            text: Raw text potentially containing markdown

        Returns:
            Cleaned text with markdown markers removed
        """
        # Remove bold markers **text**
        cleaned = re.sub(r"\*\*", "", text)
        # Remove italic markers __text__
        cleaned = re.sub(r"__", "", cleaned)
        # Remove strikethrough ~~text~~
        cleaned = re.sub(r"~~", "", cleaned)
        # Remove inline code `text`
        cleaned = re.sub(r"`", "", cleaned)
        return cleaned

    async def parse_signal(self, message: str) -> TradeSignal | None:
        """Parse a Telegram message into a structured trade signal.

        Args:
            message: The raw text content of the Telegram message

        Returns:
            TradeSignal if successfully parsed, None for non-trading messages
        """
        cleaned_message = self._strip_markdown(message)

        try:
            response_text = await self._query_groq(self.SYSTEM_PROMPT, cleaned_message)
            return self._parse_response(response_text, message)
        except Exception as e:
            print(f"Error parsing signal: {e}")
            return None

    async def _query_groq(self, system_prompt: str, user_message: str) -> str:
        """Query Groq AI and get the response text.

        Args:
            system_prompt: The system prompt with instructions
            user_message: The user message to analyze

        Returns:
            The raw response text from Groq
        """
        completion = await self.client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=1,
            max_completion_tokens=8192,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
        )

        result_text = ""
        async for chunk in completion:
            content = chunk.choices[0].delta.content
            if content:
                result_text += content

        return result_text.strip()

    def _parse_response(self, response_text: str, original_message: str) -> TradeSignal | None:
        """Parse Groq's JSON response into a TradeSignal.

        The new format always returns an actions array. This method:
        1. Parses the actions array
        2. Derives message_type from the primary action (for backward compat)
        3. Populates top-level fields from the primary action

        Args:
            response_text: The raw response from Groq
            original_message: The original Telegram message for context

        Returns:
            TradeSignal if valid, None otherwise
        """
        # Clean up potential markdown code blocks
        cleaned = re.sub(r"^```json\s*", "", response_text)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        data = json.loads(cleaned)

        # Get actions array (always present in new format)
        actions = data.get("actions", [])

        # Handle empty actions (not a trading message)
        if not actions:
            return None

        # Convert raw action dicts to ParsedAction objects
        parsed_actions = [self._dict_to_parsed_action(a) for a in actions]

        # Derive message_type from primary action (for backward compatibility)
        primary_action = parsed_actions[0]
        msg_type = self._action_to_message_type(primary_action, len(parsed_actions) > 1)

        # Extract top-level fields from primary new_signal action (if exists)
        new_signal_action = next(
            (a for a in parsed_actions if a.action_type == ActionType.NEW_SIGNAL),
            None
        )

        # Determine order type and signal completeness
        if new_signal_action:
            order_type = new_signal_action.order_type or OrderType.BUY
            stop_loss = new_signal_action.stop_loss
            take_profits = new_signal_action.take_profits
            entry_price = new_signal_action.entry_price
            is_complete = self._check_action_completeness(new_signal_action)
            if not is_complete and msg_type == MessageType.NEW_SIGNAL_COMPLETE:
                msg_type = MessageType.NEW_SIGNAL_INCOMPLETE
        else:
            order_type = OrderType.BUY
            stop_loss = None
            take_profits = []
            entry_price = None
            is_complete = True  # Non-new-signal actions don't need completeness check

        # Extract modification fields from any modification action
        mod_action = next(
            (a for a in parsed_actions if a.action_type == ActionType.MODIFICATION),
            None
        )
        new_stop_loss = mod_action.new_stop_loss if mod_action else None
        new_take_profit = mod_action.new_take_profit if mod_action else None

        # Extract partial close percentage
        partial_action = next(
            (a for a in parsed_actions if a.action_type == ActionType.PARTIAL_CLOSE),
            None
        )
        close_percentage = partial_action.close_percentage if partial_action else None

        # Extract TP hit info
        tp_action = next(
            (a for a in parsed_actions if a.action_type == ActionType.TP_HIT),
            None
        )
        tp_hit_number = tp_action.tp_hit_number if tp_action else None

        # Check for move_sl_to_entry action
        move_sl_to_entry = any(
            a.action_type == ActionType.MOVE_SL_TO_ENTRY for a in parsed_actions
        )

        # Check for full close action
        close_position = any(
            a.action_type == ActionType.FULL_CLOSE for a in parsed_actions
        )

        # Extract re-entry fields
        re_entry_action = next(
            (a for a in parsed_actions if a.action_type == ActionType.RE_ENTRY),
            None
        )
        re_entry_price = re_entry_action.re_entry_price if re_entry_action else None
        re_entry_price_max = re_entry_action.re_entry_price_max if re_entry_action else None
        # For re-entry, use its stop_loss
        if re_entry_action and re_entry_action.stop_loss:
            stop_loss = re_entry_action.stop_loss

        return TradeSignal(
            symbol=data.get("symbol", ""),
            order_type=order_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            lot_size=data.get("lot_size"),
            comment=original_message[:200],
            confidence=data.get("confidence", 0.5),
            message_type=msg_type,
            is_complete=is_complete,
            move_sl_to_entry=move_sl_to_entry,
            tp_hit_number=tp_hit_number,
            close_position=close_position,
            close_percentage=close_percentage,
            new_stop_loss=new_stop_loss,
            new_take_profit=new_take_profit,
            re_entry_price=re_entry_price,
            re_entry_price_max=re_entry_price_max,
            actions=actions,  # Keep raw dicts for backward compat with existing code
        )

    def _dict_to_parsed_action(self, action_dict: dict) -> ParsedAction:
        """Convert a raw action dict to a ParsedAction object."""
        action_type_str = action_dict.get("action_type", "")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            # Default to modification for unknown types
            action_type = ActionType.MODIFICATION

        order_type = None
        order_type_str = action_dict.get("order_type")
        if order_type_str:
            try:
                order_type = OrderType(order_type_str)
            except ValueError:
                pass

        return ParsedAction(
            action_type=action_type,
            order_type=order_type,
            entry_price=action_dict.get("entry_price"),
            entry_price_max=action_dict.get("entry_price_max"),
            stop_loss=action_dict.get("stop_loss"),
            take_profits=action_dict.get("take_profits", []),
            new_stop_loss=action_dict.get("new_stop_loss"),
            new_take_profit=action_dict.get("new_take_profit"),
            close_percentage=action_dict.get("close_percentage"),
            tp_hit_number=action_dict.get("tp_hit_number"),
            re_entry_price=action_dict.get("re_entry_price"),
            re_entry_price_max=action_dict.get("re_entry_price_max"),
        )

    def _action_to_message_type(self, action: ParsedAction, has_multiple: bool) -> MessageType:
        """Convert a ParsedAction to its corresponding MessageType.

        Args:
            action: The primary action
            has_multiple: True if there are multiple actions (returns COMPOUND_ACTION)

        Returns:
            The corresponding MessageType
        """
        if has_multiple:
            return MessageType.COMPOUND_ACTION

        action_type_map = {
            ActionType.NEW_SIGNAL: MessageType.NEW_SIGNAL_COMPLETE,
            ActionType.MODIFICATION: MessageType.MODIFICATION,
            ActionType.MOVE_SL_TO_ENTRY: MessageType.MODIFICATION,  # Treat as modification
            ActionType.PARTIAL_CLOSE: MessageType.PARTIAL_CLOSE,
            ActionType.FULL_CLOSE: MessageType.CLOSE_SIGNAL,
            ActionType.TP_HIT: MessageType.PROFIT_NOTIFICATION,
            ActionType.RE_ENTRY: MessageType.RE_ENTRY,
        }
        return action_type_map.get(action.action_type, MessageType.NOT_TRADING)

    def _check_action_completeness(self, action: ParsedAction) -> bool:
        """Check if a new_signal action has all required fields.

        Market orders (buy/sell): Only need SL and TP
        Pending orders (limit/stop): Also need entry_price
        """
        if action.action_type != ActionType.NEW_SIGNAL:
            return True

        has_sl = action.stop_loss is not None
        has_tp = len(action.take_profits) > 0
        has_entry = action.entry_price is not None

        if action.order_type and action.order_type.value in ["buy_limit", "sell_limit", "buy_stop", "sell_stop"]:
            return has_sl and has_tp and has_entry
        else:
            # Market orders only need SL and TP
            return has_sl and has_tp

    def _check_completeness(self, data: dict, msg_type: MessageType) -> bool:
        """Check if a new signal has all required fields (backward compatible).

        This method is kept for backward compatibility with existing tests.
        It wraps the new action-based completeness check.

        Market orders (buy/sell): Only need SL and TP
        Pending orders (limit/stop): Also need entry_price

        Args:
            data: Parsed data dict with order_type, stop_loss, take_profits, entry_price
            msg_type: The message type classification

        Returns:
            True if the signal has all required fields for its order type
        """
        if msg_type not in [MessageType.NEW_SIGNAL_COMPLETE, MessageType.NEW_SIGNAL_INCOMPLETE]:
            return True

        has_sl = data.get("stop_loss") is not None
        has_tp = len(data.get("take_profits", [])) > 0
        has_entry = data.get("entry_price") is not None

        order_type = data.get("order_type", "")
        is_pending_order = order_type in ["buy_limit", "sell_limit", "buy_stop", "sell_stop"]

        if is_pending_order:
            return has_sl and has_tp and has_entry
        else:
            # Market orders only need SL and TP
            return has_sl and has_tp


    async def parse_correction(
        self,
        correction_text: str,
        original_entry: float | None,
        original_sl: float | None,
        original_tps: list[float],
        symbol: str,
        order_type: str,
    ) -> dict | None:
        """Parse a shorthand correction message with context of the original signal.

        Args:
            correction_text: The correction message (e.g., "44*", "SL 2640")
            original_entry: Original entry price from the signal
            original_sl: Original stop loss from the signal
            original_tps: Original take profit levels from the signal
            symbol: Trading symbol (e.g., "XAUUSD")
            order_type: Order type (e.g., "buy", "sell")

        Returns:
            Dict with corrected values, or None if parsing failed
        """
        system_prompt = self.CORRECTION_SYSTEM_PROMPT.format(
            original_entry=original_entry,
            original_sl=original_sl,
            original_tps=original_tps,
            symbol=symbol,
            order_type=order_type,
        )

        try:
            response_text = await self._query_groq(system_prompt, correction_text)
            return self._parse_correction_response(response_text)
        except Exception as e:
            print(f"Error parsing correction: {e}")
            return None

    def _parse_correction_response(self, response_text: str) -> dict | None:
        """Parse Groq's JSON response for a correction.

        Args:
            response_text: The raw response from Groq

        Returns:
            Dict with corrected values, or None if invalid
        """
        # Clean up potential markdown code blocks
        cleaned = re.sub(r"^```json\s*", "", response_text)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
            return {
                "corrected_entry": data.get("corrected_entry"),
                "corrected_stop_loss": data.get("corrected_stop_loss"),
                "corrected_take_profits": data.get("corrected_take_profits"),
                "confidence": data.get("confidence", 0.5),
                "interpretation": data.get("interpretation", ""),
            }
        except json.JSONDecodeError as e:
            print(f"Error parsing correction JSON: {e}")
            return None
