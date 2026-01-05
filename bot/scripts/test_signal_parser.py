"""
Test script to verify Claude signal parsing on logged messages.

Tests all 7 message types:
1. NEW_SIGNAL_COMPLETE - Complete signal with SL, TP, Entry
2. NEW_SIGNAL_INCOMPLETE - Missing SL/TP/Entry
3. MODIFICATION - Update SL/TP
4. RE_ENTRY - New entry/SL for re-entry
5. PROFIT_NOTIFICATION - TP hit, profit info
6. CLOSE_SIGNAL - Close position
7. NOT_TRADING - Non-trading message

Usage:
    uv run python scripts/test_signal_parser.py
    uv run python scripts/test_signal_parser.py path/to/messages.log
"""

import asyncio
import re
import sys


def parse_log_file(file_path: str) -> list[dict]:
    """Parse telegram_messages.log into individual messages."""
    with open(file_path) as f:
        content = f.read()

    messages: list[dict] = []

    # Split by message markers
    pattern = r"--- Message \d+ ---\n(.*?)(?=--- Message \d+ ---|$)"
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        msg: dict = {"id": None, "date": None, "reply_to": None, "text": ""}

        lines = match.strip().split("\n")
        text_started = False
        text_lines: list[str] = []

        for line in lines:
            if line.startswith("ID: "):
                msg["id"] = line[4:]
            elif line.startswith("Date: "):
                msg["date"] = line[6:]
            elif line.startswith("Reply to: "):
                msg["reply_to"] = line[10:]
            elif line == "Text:":
                text_started = True
            elif text_started:
                text_lines.append(line)

        msg["text"] = "\n".join(text_lines).strip()
        if msg["text"] and msg["text"] != "(no text)":
            messages.append(msg)

    return messages


def get_message_type_color(msg_type: str) -> str:
    """Get ANSI color code for message type."""
    colors = {
        "new_signal_complete": "\033[92m",  # Green
        "new_signal_incomplete": "\033[93m",  # Yellow
        "modification": "\033[94m",  # Blue
        "re_entry": "\033[95m",  # Magenta
        "profit_notification": "\033[96m",  # Cyan
        "close_signal": "\033[91m",  # Red
        "not_trading": "\033[90m",  # Gray
    }
    return colors.get(msg_type, "\033[0m")


async def main() -> None:
    """Test signal parsing on logged messages."""
    # Import here to avoid import errors if running without deps
    from tania_signal_copier import SignalParser

    log_file = sys.argv[1] if len(sys.argv) > 1 else "telegram_messages.log"

    print(f"Reading messages from: {log_file}")
    print()

    try:
        messages = parse_log_file(log_file)
    except FileNotFoundError:
        print(f"Error: File not found: {log_file}")
        print("Run test_telegram.py first to fetch messages.")
        return

    print(f"Found {len(messages)} messages with text content")
    print()

    parser = SignalParser()

    # Count by message type
    type_counts: dict[str, int] = {
        "new_signal_complete": 0,
        "new_signal_incomplete": 0,
        "modification": 0,
        "re_entry": 0,
        "profit_notification": 0,
        "close_signal": 0,
        "not_trading": 0,
    }

    for msg in messages:
        print("=" * 70)
        print(f"Message ID: {msg['id']}")
        if msg["reply_to"]:
            print(f"Reply to: {msg['reply_to']}")
        print(f"Text:\n{msg['text'][:200]}{'...' if len(msg['text']) > 200 else ''}")
        print()

        print("Parsing with Claude...")
        signal = await parser.parse_signal(msg["text"])

        if signal is None:
            type_counts["not_trading"] += 1
            color = get_message_type_color("not_trading")
            print(f"{color}TYPE: NOT_TRADING\033[0m")
            print("  (Non-trading message)")
        else:
            msg_type = signal.message_type.value
            type_counts[msg_type] += 1
            color = get_message_type_color(msg_type)

            print(f"{color}TYPE: {msg_type.upper()}\033[0m")
            print(f"  Confidence: {signal.confidence:.0%}")
            print(f"  Complete: {signal.is_complete}")

            if signal.symbol:
                print(f"  Symbol: {signal.symbol}")
            if signal.order_type:
                print(f"  Order Type: {signal.order_type.value}")

            # Show type-specific fields
            if msg_type in ["new_signal_complete", "new_signal_incomplete"]:
                print(f"  Entry: {signal.entry_price or 'Market'}")
                print(f"  SL: {signal.stop_loss}")
                print(f"  TP: {signal.take_profits}")

            elif msg_type == "modification":
                print(f"  New SL: {signal.new_stop_loss}")
                print(f"  New TP: {signal.new_take_profit}")

            elif msg_type == "re_entry":
                print(f"  Re-entry Price: {signal.re_entry_price}")
                if signal.re_entry_price_max:
                    print(f"  Re-entry Max: {signal.re_entry_price_max}")
                print(f"  New SL: {signal.new_stop_loss or signal.stop_loss}")

            elif msg_type == "profit_notification":
                print(f"  Move SL to Entry: {signal.move_sl_to_entry}")

            elif msg_type == "close_signal":
                print(f"  Close Position: {signal.close_position}")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY BY MESSAGE TYPE:")
    print("-" * 40)
    total = sum(type_counts.values())
    for msg_type, count in type_counts.items():
        color = get_message_type_color(msg_type)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {color}{msg_type.upper():25}\033[0m: {count:3} ({pct:5.1f}%)")
    print("-" * 40)
    print(f"  {'TOTAL':25}: {total:3}")


if __name__ == "__main__":
    asyncio.run(main())
