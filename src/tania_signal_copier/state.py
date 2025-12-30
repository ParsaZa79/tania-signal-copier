"""
State management for the Telegram MT5 Signal Bot.

This module handles persistent state tracking between Telegram messages
and MT5 positions, including JSON serialization and cleanup.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from tania_signal_copier.models import TrackedPosition


class BotState:
    """Persistent state manager for the bot.

    Maintains mappings between Telegram message IDs and MT5 positions,
    with automatic JSON persistence and cleanup of old records.

    Attributes:
        positions: Dict mapping telegram_msg_id to TrackedPosition
        ticket_to_msg_id: Reverse lookup from MT5 ticket to message ID
        last_signal_msg_id: ID of the most recent signal message
    """

    DEFAULT_STATE_FILE = "bot_state.json"
    MAX_RECORDS = 20

    def __init__(self, state_file: str | Path | None = None) -> None:
        """Initialize state manager.

        Args:
            state_file: Path to the JSON state file. Defaults to bot_state.json.
        """
        self.state_file = Path(state_file or self.DEFAULT_STATE_FILE)
        self.positions: dict[int, TrackedPosition] = {}
        self.ticket_to_msg_id: dict[int, int] = {}
        self.last_signal_msg_id: int | None = None

    def add_position(self, position: TrackedPosition) -> None:
        """Add a tracked position to state.

        Args:
            position: The position to track
        """
        self.positions[position.telegram_msg_id] = position
        self.ticket_to_msg_id[position.mt5_ticket] = position.telegram_msg_id
        self.last_signal_msg_id = position.telegram_msg_id

    def get_position_by_msg_id(self, msg_id: int) -> TrackedPosition | None:
        """Get position by Telegram message ID.

        Args:
            msg_id: The Telegram message ID

        Returns:
            TrackedPosition if found, None otherwise
        """
        return self.positions.get(msg_id)

    def get_position_by_ticket(self, ticket: int) -> TrackedPosition | None:
        """Get position by MT5 ticket number.

        Args:
            ticket: The MT5 position ticket

        Returns:
            TrackedPosition if found, None otherwise
        """
        msg_id = self.ticket_to_msg_id.get(ticket)
        if msg_id is not None:
            return self.positions.get(msg_id)
        return None

    def remove_position(self, msg_id: int) -> None:
        """Remove a position from tracking.

        Args:
            msg_id: The Telegram message ID to remove
        """
        position = self.positions.pop(msg_id, None)
        if position is not None:
            self.ticket_to_msg_id.pop(position.mt5_ticket, None)

    def _cleanup_old_records(self) -> None:
        """Keep only the last MAX_RECORDS positions (sorted by opened_at)."""
        if len(self.positions) <= self.MAX_RECORDS:
            return

        sorted_positions = sorted(
            self.positions.items(),
            key=lambda x: x[1].opened_at,
            reverse=True,
        )[: self.MAX_RECORDS]

        self.positions = dict(sorted_positions)
        self.ticket_to_msg_id = {
            pos.mt5_ticket: msg_id for msg_id, pos in self.positions.items()
        }

    def save(self) -> None:
        """Save state to JSON file with automatic cleanup."""
        self._cleanup_old_records()

        data = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "last_signal_msg_id": self.last_signal_msg_id,
            "positions": {
                str(msg_id): pos.to_dict() for msg_id, pos in self.positions.items()
            },
            "ticket_to_msg_id": {
                str(ticket): msg_id
                for ticket, msg_id in self.ticket_to_msg_id.items()
            },
        }

        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load state from JSON file.

        If the file doesn't exist or is corrupted, starts with empty state.
        """
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            self.last_signal_msg_id = data.get("last_signal_msg_id")

            for msg_id_str, pos_data in data.get("positions", {}).items():
                position = TrackedPosition.from_dict(pos_data)
                self.positions[int(msg_id_str)] = position

            self.ticket_to_msg_id = {
                int(k): v for k, v in data.get("ticket_to_msg_id", {}).items()
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Warning: Error loading state file: {e}")
            # Start with empty state on error
            self.positions = {}
            self.ticket_to_msg_id = {}
            self.last_signal_msg_id = None

    def __len__(self) -> int:
        """Return the number of tracked positions."""
        return len(self.positions)

    def __contains__(self, msg_id: int) -> bool:
        """Check if a message ID is tracked."""
        return msg_id in self.positions
