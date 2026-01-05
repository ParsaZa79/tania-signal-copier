#!/usr/bin/env python3
"""
Setup Telegram session for testing.

Run this script once to authenticate with Telegram and create a session file.
The session file will be reused by the integration tests.

Usage:
    uv run python scripts/setup_telegram_session.py
"""

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient

# Load environment variables
load_dotenv()

SESSION_NAME = "signal_bot_session"


async def main() -> None:
    """Authenticate with Telegram and create session file."""
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    channel = os.getenv("TELEGRAM_CHANNEL", "")

    if api_id == 0 or not api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        return

    print("=" * 60)
    print("TELEGRAM SESSION SETUP")
    print("=" * 60)
    print(f"API ID: {api_id}")
    print(f"Channel: {channel}")
    print("=" * 60)
    print()
    print("You will be prompted to enter your phone number and")
    print("the verification code sent to your Telegram app.")
    print()

    client = TelegramClient(SESSION_NAME, api_id, api_hash)

    await client.start()

    print()
    print("=" * 60)
    print("SUCCESS! Session created.")
    print("=" * 60)

    # Test the connection
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")

    if channel:
        try:
            entity = await client.get_entity(channel)
            title = getattr(entity, "title", channel)
            print(f"Channel found: {title}")

            # Fetch a sample message
            messages = await client.get_messages(entity, limit=1)
            if messages:
                print(f"Latest message preview: {(messages[0].text or '')[:50]}...")
        except Exception as e:
            print(f"Could not access channel: {e}")

    print()
    print(f"Session file created: {SESSION_NAME}.session")
    print("You can now run the integration tests!")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
