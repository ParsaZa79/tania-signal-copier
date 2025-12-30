"""
Test script to fetch last 10 messages from the configured Telegram channel.

Usage:
    uv run python scripts/test_telegram.py
"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "")


async def main() -> None:
    """Fetch and display last 10 messages from the channel."""
    print("Connecting to Telegram...")
    print(f"  API ID: {API_ID}")
    print(f"  Channel: {CHANNEL}")
    print()

    client = TelegramClient("signal_bot_session", API_ID, API_HASH)

    await client.start()  # type: ignore[misc]
    print("Connected to Telegram!\n")

    log_lines: list[str] = []
    try:
        # Get channel entity
        channel = await client.get_entity(CHANNEL)
        channel_name = getattr(channel, "title", CHANNEL)
        print(f"Channel: {channel_name}")
        print("=" * 60)
        print()

        log_lines.append(f"Channel: {channel_name}\n")
        log_lines.append(f"Fetched at: {datetime.now().isoformat()}\n")
        log_lines.append("=" * 60 + "\n\n")

        # Fetch last 10 messages
        messages = await client.get_messages(channel, limit=10)  # type: ignore[misc]

        for i, msg in enumerate(messages, 1):  # type: ignore[arg-type]
            print(f"--- Message {i} ---")
            print(f"ID: {msg.id}")
            print(f"Date: {msg.date}")
            print("Text:")
            print(msg.text or "(no text - possibly media)")
            print()

            log_lines.append(f"--- Message {i} ---\n")
            log_lines.append(f"ID: {msg.id}\n")
            log_lines.append(f"Date: {msg.date}\n")
            log_lines.append(f"Text:\n{msg.text or '(no text)'}\n\n")

    except Exception as e:
        print(f"Error: {e}")

    await client.disconnect()  # type: ignore[misc]

    # Save to file (after async operations)
    if log_lines:
        log_file = "telegram_messages.log"
        with open(log_file, "w") as f:  # noqa: ASYNC230
            f.writelines(log_lines)
        print(f"Messages saved to: {log_file}")


if __name__ == "__main__":
    asyncio.run(main())
