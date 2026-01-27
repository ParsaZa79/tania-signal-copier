#!/usr/bin/env python3
"""Fetch recent Telegram channel messages for offline analysis."""

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "TaniaTradingAcademy")
# Session file is in the bot directory (parent of scripts) - matches config.py
SESSION_NAME = str(Path(__file__).parent.parent / "signal_bot_session")

# Fetch settings (CLI overridable)
DEFAULT_BATCH_SIZE = 50
DEFAULT_TOTAL_MESSAGES = 200
DEFAULT_DELAY_SECONDS = 5.0

# Output file
OUTPUT_DIR = Path(__file__).parent.parent / "analysis"
OUTPUT_FILE = OUTPUT_DIR / "signals_raw.json"


def parse_args() -> argparse.Namespace:
    """Parse CLI args with env var fallbacks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--total",
        type=int,
        default=int(os.getenv("TELEGRAM_FETCH_TOTAL", str(DEFAULT_TOTAL_MESSAGES))),
        help="Total messages to fetch (default: 200 or TELEGRAM_FETCH_TOTAL).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("TELEGRAM_FETCH_BATCH", str(DEFAULT_BATCH_SIZE))),
        help="Batch size per request (default: 50 or TELEGRAM_FETCH_BATCH).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=float(os.getenv("TELEGRAM_FETCH_DELAY", str(DEFAULT_DELAY_SECONDS))),
        help="Delay between batches in seconds (default: 5 or TELEGRAM_FETCH_DELAY).",
    )
    return parser.parse_args()


async def fetch_messages(total_messages: int, batch_size: int, delay_seconds: float) -> None:
    """Fetch messages from Telegram channel in batches."""
    print("Connecting to Telegram...")
    print(f"API ID: {API_ID}")
    print(f"Channel: {CHANNEL}")
    print(f"Target messages: {total_messages}")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Not authorized. Please run the bot first to authenticate.")
        return

    print("Connected to Telegram!")

    # Get channel entity
    try:
        channel = await client.get_entity(CHANNEL)
        channel_name = getattr(channel, "title", CHANNEL)
        print(f"Found channel: {channel_name}")
    except Exception as e:
        print(f"Error getting channel: {e}")
        await client.disconnect()
        return

    # Fetch messages in batches
    all_messages = []
    offset_id = 0
    batches_needed = (total_messages + batch_size - 1) // batch_size

    for batch_num in range(batches_needed):
        print(f"\nFetching batch {batch_num + 1}/{batches_needed}...")

        messages = []
        async for msg in client.iter_messages(channel, limit=batch_size, offset_id=offset_id):
            msg_data = {
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": msg.text or "",
                "reply_to_msg_id": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
                "forward_from": None,
                "forward_date": None,
            }

            # Check if forwarded
            if msg.forward:
                if msg.forward.from_name:
                    msg_data["forward_from"] = msg.forward.from_name
                elif msg.forward.from_id:
                    msg_data["forward_from"] = str(msg.forward.from_id)
                if msg.forward.date:
                    msg_data["forward_date"] = msg.forward.date.isoformat()

            messages.append(msg_data)
            offset_id = msg.id  # Update for next batch

        all_messages.extend(messages)
        print(f"  Fetched {len(messages)} messages (total: {len(all_messages)})")

        # Save incrementally
        save_messages(all_messages)

        # Stop if we have enough or no more messages
        if len(messages) < batch_size or len(all_messages) >= total_messages:
            break

        # Wait before next batch
        if batch_num < batches_needed - 1:
            print(f"  Waiting {delay_seconds}s before next batch...")
            await asyncio.sleep(delay_seconds)

    await client.disconnect()

    print(f"\nDone! Fetched {len(all_messages)} messages total.")
    print(f"Saved to: {OUTPUT_FILE}")

    # Print summary
    print_summary(all_messages)


def save_messages(messages: list) -> None:
    """Save messages to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_data = {
        "fetched_at": datetime.now().isoformat(),
        "channel": CHANNEL,
        "total_messages": len(messages),
        "messages": messages,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def print_summary(messages: list) -> None:
    """Print summary of fetched messages."""
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    # Count messages with text
    with_text = sum(1 for m in messages if m["text"].strip())
    with_replies = sum(1 for m in messages if m["reply_to_msg_id"])

    print(f"Total messages: {len(messages)}")
    print(f"With text content: {with_text}")
    print(f"Replies to other messages: {with_replies}")

    if messages:
        # Date range
        dates = [m["date"] for m in messages if m["date"]]
        if dates:
            oldest = min(dates)
            newest = max(dates)
            print(f"Date range: {oldest[:10]} to {newest[:10]}")

    # Sample some messages
    print("\n--- Sample Messages ---")
    for i, msg in enumerate(messages[:5]):
        text_preview = msg["text"][:100].replace("\n", " ")
        reply_info = f" (reply to {msg['reply_to_msg_id']})" if msg["reply_to_msg_id"] else ""
        print(f"{i+1}. [{msg['id']}]{reply_info}: {text_preview}...")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(fetch_messages(args.total, args.batch_size, args.delay))
