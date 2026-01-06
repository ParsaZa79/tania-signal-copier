"""
Signal parser for the Telegram MT5 Signal Bot.

This module uses Claude AI to parse and classify trading signals
from Telegram messages into structured TradeSignal objects.
"""

import json
import re

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, TextBlock

from tania_signal_copier.models import MessageType, OrderType, TradeSignal


class SignalParser:
    """Uses Claude AI to parse trading signals from various formats.

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

    PARSER_PROMPT = """Analyze this forex/gold trading message and classify it.

CLASSIFICATION RULES:
1. NEW_SIGNAL_COMPLETE: Contains symbol + direction (buy/sell) + entry price + stop loss + at least one take profit
2. NEW_SIGNAL_INCOMPLETE: Contains symbol + direction but MISSING one or more of: entry price, stop loss, take profit
3. MODIFICATION: Updates SL/TP for an existing trade (often says "move SL to...", "update SL/TP", "new SL")
4. RE_ENTRY: Provides new entry price/range and SL for the same symbol (contains "re-entry", "re entry", or new entry levels as reply)
5. PROFIT_NOTIFICATION: Reports TP hit, pips profit, trade result.
   CRITICAL - "move_sl_to_entry" and "tp_hit_number" rules:
   - "tp_hit_number": ONLY set if message EXPLICITLY confirms a TP was hit (e.g., "TP1 hit", "First target reached", "TP2 ✅", "Target 1 done"). Otherwise null.
   - "move_sl_to_entry": true ONLY if:
     (a) A specific TP is CONFIRMED hit in the message, OR
     (b) Explicit instruction like "move SL to entry", "SL to breakeven", "secure at entry"
   - "move_sl_to_entry": false for:
     (a) "Book some profits", "Secure profits", "Take some profits" - these are SUGGESTIONS to manually close partial, NOT instructions to move SL
     (b) Pips running messages like "+50 pips", "35 pips profit running" - just informational
     (c) Any message that does NOT explicitly confirm a TP hit or say "move SL"
6. CLOSE_SIGNAL: Explicitly says to close a position (e.g., "close gold", "exit trade", "close all")
7. COMPOUND_ACTION: Contains MULTIPLE distinct actions in ONE message (e.g., "Add Sell-Limit..." AND "Update SL to..."). Use this when a message contains BOTH a new pending order AND a modification to an existing position.
8. NOT_TRADING: Advertisements, announcements, greetings, or non-trading content

For COMPOUND_ACTION, return an "actions" array with each action separately identified.

ORDER TYPE RULES (CRITICAL):
- "buy" or "sell" = MARKET orders (execute immediately at current price). Use these for signals like "BUY GOLD @", "SELL XAUUSD @", etc. The entry price in these signals is just a reference zone, NOT a pending order trigger.
- "buy_limit", "sell_limit", "buy_stop", "sell_stop" = PENDING orders. ONLY use these if the message EXPLICITLY contains the words "limit" or "stop" (e.g., "Buy Limit", "Sell-Limit", "buy stop", "SELL STOP").
- If the message says "BUY @ 4340" or "SELL @ 4340" WITHOUT the word "limit" or "stop", use "buy" or "sell" (market order).

Return JSON:
{{
    "message_type": "new_signal_complete|new_signal_incomplete|modification|re_entry|profit_notification|close_signal|compound_action|not_trading",
    "symbol": "XAUUSD" or null,
    "order_type": "buy|sell|buy_limit|sell_limit|buy_stop|sell_stop" or null,
    "entry_price": number or null,
    "entry_price_max": number or null (for ranges like "4280-4283"),
    "stop_loss": number or null,
    "take_profits": [numbers] or [],
    "new_stop_loss": number or null (for modifications),
    "new_take_profit": number or null (for modifications),
    "re_entry_price": number or null (for re-entry signals),
    "re_entry_price_max": number or null (for re-entry range like "4284-4286"),
    "move_sl_to_entry": true/false (from profit notification),
    "tp_hit_number": 1|2|3|...|null (which TP was hit, e.g., 1 for TP1, 2 for TP2),
    "close_position": true/false,
    "actions": [
        {{
            "action_type": "new_signal|modification",
            "order_type": "buy_limit|sell_limit|buy_stop|sell_stop" or null,
            "entry_price": number or null,
            "entry_price_max": number or null,
            "stop_loss": number or null,
            "take_profits": [numbers] or [],
            "new_stop_loss": number or null,
            "new_take_profit": number or null
        }}
    ],
    "confidence": 0-1
}}

Note: The "actions" array is ONLY used for compound_action message_type. For other types, leave it empty [].

Message:
```
{message}
```

Return ONLY valid JSON, no explanation."""

    def __init__(self) -> None:
        """Initialize parser.

        Uses Claude Code subscription auth (no API key needed).
        """
        pass

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
        # Strip markdown formatting that can corrupt number parsing
        cleaned_message = self._strip_markdown(message)
        prompt = self.PARSER_PROMPT.format(message=cleaned_message)

        try:
            response_text = await self._query_claude(prompt)
            return self._parse_response(response_text, message)
        except Exception as e:
            print(f"Error parsing signal: {e}")
            return None

    async def _query_claude(self, prompt: str) -> str:
        """Query Claude AI and get the response text.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            The raw response text from Claude
        """
        options = ClaudeAgentOptions(
            model="opus", # Use Haiku model for the fastest response
            allowed_tools=[],  # No tools needed for parsing
            max_turns=1,  # Single turn for parsing
        )

        result_text = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        result_text += block.text

        return result_text.strip()

    def _parse_response(self, response_text: str, original_message: str) -> TradeSignal | None:
        """Parse Claude's JSON response into a TradeSignal.

        Args:
            response_text: The raw response from Claude
            original_message: The original Telegram message for context

        Returns:
            TradeSignal if valid, None otherwise
        """
        # Clean up potential markdown code blocks
        cleaned = re.sub(r"^```json\s*", "", response_text)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        data = json.loads(cleaned)

        # Determine message type
        msg_type = self._get_message_type(data)
        if msg_type == MessageType.NOT_TRADING:
            return None

        # Check completeness for new signals
        is_complete = self._check_completeness(data, msg_type)
        if not is_complete and msg_type == MessageType.NEW_SIGNAL_COMPLETE:
            msg_type = MessageType.NEW_SIGNAL_INCOMPLETE

        # Get order type
        order_type = self._get_order_type(data)

        return TradeSignal(
            symbol=data.get("symbol", ""),
            order_type=order_type,
            entry_price=data.get("entry_price"),
            stop_loss=data.get("stop_loss"),
            take_profits=data.get("take_profits", []),
            lot_size=data.get("lot_size"),
            comment=original_message[:200],
            confidence=data.get("confidence", 0.5),
            message_type=msg_type,
            is_complete=is_complete,
            move_sl_to_entry=data.get("move_sl_to_entry", False),
            tp_hit_number=data.get("tp_hit_number"),
            close_position=data.get("close_position", False),
            new_stop_loss=data.get("new_stop_loss"),
            new_take_profit=data.get("new_take_profit"),
            re_entry_price=data.get("re_entry_price"),
            re_entry_price_max=data.get("re_entry_price_max"),
            actions=data.get("actions", []),
        )

    def _get_message_type(self, data: dict) -> MessageType:
        """Extract and validate message type from parsed data."""
        msg_type_str = data.get("message_type", "not_trading")
        try:
            return MessageType(msg_type_str)
        except ValueError:
            return MessageType.NOT_TRADING

    def _check_completeness(self, data: dict, msg_type: MessageType) -> bool:
        """Check if a new signal has all required fields."""
        if msg_type not in [MessageType.NEW_SIGNAL_COMPLETE, MessageType.NEW_SIGNAL_INCOMPLETE]:
            return True

        has_sl = data.get("stop_loss") is not None
        has_tp = len(data.get("take_profits", [])) > 0
        has_entry = data.get("entry_price") is not None

        return has_sl and has_tp and has_entry

    def _get_order_type(self, data: dict) -> OrderType:
        """Extract order type from parsed data with fallback."""
        order_type_str = data.get("order_type")
        if order_type_str:
            try:
                return OrderType(order_type_str)
            except ValueError:
                pass
        return OrderType.BUY  # Default fallback
