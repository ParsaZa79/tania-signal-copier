"""Telegram channels router."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Path to bot session file
BOT_DIR = Path(__file__).parent.parent.parent.parent / "bot"
SESSION_PATH = BOT_DIR / "signal_bot_session.session"


@router.get("/channels")
async def get_telegram_channels(api_id: int, api_hash: str):
    """Get list of available Telegram channels/groups.

    Requires api_id and api_hash as query parameters.
    Copies session to temp file to avoid locking issues if bot is running.

    Returns list of channels with:
    - id: Channel/group ID (string)
    - name: Display name
    - username: Username for public channels (optional)
    - type: "channel" | "group"
    """
    if not SESSION_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Telegram session not found. Please run the bot first to create a session.",
        )

    if api_id <= 0 or not api_hash:
        raise HTTPException(status_code=400, detail="Invalid API credentials")

    try:
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Telethon library not installed",
        ) from e

    # Copy session to temp file to avoid lock issues with running bot
    temp_session = None
    temp_dir = None

    try:
        temp_dir = tempfile.mkdtemp()
        temp_session = Path(temp_dir) / "temp_session"
        shutil.copy(SESSION_PATH, temp_session.with_suffix(".session"))

        async def _fetch() -> list[dict]:
            channels: list[dict] = []
            client = TelegramClient(str(temp_session), api_id, api_hash)

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    raise HTTPException(
                        status_code=401,
                        detail="Telegram session not authorized. Run the bot to authenticate.",
                    )

                # Get all dialogs (chats, channels, groups)
                async for dialog in client.iter_dialogs():
                    entity = dialog.entity

                    # Include channels and megagroups (supergroups)
                    if isinstance(entity, Channel):
                        title = entity.title or "Untitled"

                        if entity.username:
                            # Public channel - use username as value
                            channels.append({
                                "id": entity.username,
                                "name": title,
                                "username": entity.username,
                                "type": "channel" if entity.broadcast else "group",
                            })
                        else:
                            # Private channel - use ID as value
                            channels.append({
                                "id": str(entity.id),
                                "name": f"{title} ({entity.id})",
                                "username": None,
                                "type": "channel" if entity.broadcast else "group",
                            })

                    elif isinstance(entity, Chat):
                        # Regular groups (not supergroups)
                        title = entity.title or "Untitled"
                        channels.append({
                            "id": str(entity.id),
                            "name": f"{title} ({entity.id})",
                            "username": None,
                            "type": "group",
                        })

            finally:
                await client.disconnect()  # type: ignore[misc]

            return channels

        # Run async function
        channels = await _fetch()

        # Sort alphabetically by display name
        channels.sort(key=lambda x: x["name"].lower())

        return {"channels": channels}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch channels: {e}") from e

    finally:
        # Clean up temp session files
        if temp_session:
            for suffix in ["", ".session", ".session-journal"]:
                temp_file = temp_session.with_suffix(suffix) if suffix else temp_session
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

            if temp_dir:
                try:
                    Path(temp_dir).rmdir()
                except OSError:
                    pass
