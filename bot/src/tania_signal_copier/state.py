"""
State management for the Telegram MT5 Signal Bot.

This module handles persistent state tracking between Telegram messages
and MT5 positions, including JSON serialization and cleanup.

Version 2 introduces DualPosition support for dual-trade strategies.
Version 3 adds original signal data for edit detection.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from tania_signal_copier.models import (
    DualPosition,
    PositionStatus,
    TrackedPosition,
    TradeRole,
)


class BotState:
    """Persistent state manager for the bot.

    Maintains mappings between Telegram message IDs and MT5 positions,
    with automatic JSON persistence and cleanup of old records.

    Version 2 stores DualPosition objects to support dual-trade strategies.
    Version 3 adds original signal data (original_message_text, original_stop_loss,
    original_take_profits) to TrackedPosition for edit detection.

    Attributes:
        positions: Dict mapping telegram_msg_id to DualPosition
        ticket_to_msg_id: Reverse lookup from MT5 ticket to message ID
        last_signal_msg_id: ID of the most recent signal message
    """

    DEFAULT_STATE_FILE = "bot_state.json"
    MAX_RECORDS = 20
    CURRENT_VERSION = 3  # v3: original signal data for edit detection

    def __init__(self, state_file: str | Path | None = None) -> None:
        """Initialize state manager.

        Args:
            state_file: Path to the JSON state file. Defaults to bot_state.json.
        """
        self.state_file = Path(state_file or self.DEFAULT_STATE_FILE)
        self.positions: dict[int, DualPosition] = {}
        self.ticket_to_msg_id: dict[int, int] = {}
        self.last_signal_msg_id: int | None = None

    def add_position(self, position: TrackedPosition, role: TradeRole) -> None:
        """Add a tracked position to state with specified role.

        Args:
            position: The position to track
            role: The role of this position (SCALP, RUNNER, or SINGLE)
        """
        msg_id = position.telegram_msg_id
        position.role = role

        # Get or create DualPosition
        if msg_id not in self.positions:
            self.positions[msg_id] = DualPosition(telegram_msg_id=msg_id)

        dual = self.positions[msg_id]

        # Assign to appropriate slot
        if role == TradeRole.RUNNER:
            dual.runner = position
        else:
            # SCALP or SINGLE both go to scalp slot
            dual.scalp = position

        # Update reverse lookup
        self.ticket_to_msg_id[position.mt5_ticket] = msg_id
        self.last_signal_msg_id = msg_id

    def get_dual_position_by_msg_id(self, msg_id: int) -> DualPosition | None:
        """Get DualPosition by Telegram message ID.

        Args:
            msg_id: The Telegram message ID

        Returns:
            DualPosition if found, None otherwise
        """
        return self.positions.get(msg_id)

    def get_position_by_msg_id(self, msg_id: int) -> TrackedPosition | None:
        """Get scalp position by Telegram message ID (backward compat).

        Args:
            msg_id: The Telegram message ID

        Returns:
            TrackedPosition (scalp) if found, None otherwise
        """
        dual = self.positions.get(msg_id)
        return dual.scalp if dual else None

    def get_position_by_role(
        self, msg_id: int, role: TradeRole
    ) -> TrackedPosition | None:
        """Get position by message ID and role.

        Args:
            msg_id: The Telegram message ID
            role: The trade role to get

        Returns:
            TrackedPosition if found, None otherwise
        """
        dual = self.positions.get(msg_id)
        return dual.get_by_role(role) if dual else None

    def get_scalp_by_msg_id(self, msg_id: int) -> TrackedPosition | None:
        """Convenience method to get scalp position."""
        return self.get_position_by_role(msg_id, TradeRole.SCALP)

    def get_runner_by_msg_id(self, msg_id: int) -> TrackedPosition | None:
        """Convenience method to get runner position."""
        return self.get_position_by_role(msg_id, TradeRole.RUNNER)

    def get_position_by_ticket(
        self, ticket: int
    ) -> tuple[TrackedPosition, TradeRole] | None:
        """Get position and its role by MT5 ticket number.

        Args:
            ticket: The MT5 position ticket

        Returns:
            Tuple of (TrackedPosition, TradeRole) if found, None otherwise
        """
        msg_id = self.ticket_to_msg_id.get(ticket)
        if msg_id is None:
            return None

        dual = self.positions.get(msg_id)
        if dual is None:
            return None

        if dual.scalp and dual.scalp.mt5_ticket == ticket:
            return (dual.scalp, dual.scalp.role)
        if dual.runner and dual.runner.mt5_ticket == ticket:
            return (dual.runner, dual.runner.role)
        return None

    def get_pending_position_by_symbol(self, symbol: str) -> DualPosition | None:
        """Get pending (incomplete) dual position by symbol.

        Finds the most recent position that is still pending completion
        for the given symbol.

        Args:
            symbol: The trading symbol (e.g., "XAUUSD")

        Returns:
            DualPosition if found, None otherwise
        """
        pending_duals = []

        for dual in self.positions.values():
            # Check if any position in the dual matches
            for pos in dual.all_positions:
                if pos.symbol == symbol and pos.status == PositionStatus.PENDING_COMPLETION:
                    pending_duals.append((dual, pos.opened_at))
                    break

        if not pending_duals:
            return None

        # Return the most recent pending dual position
        return max(pending_duals, key=lambda x: x[1])[0]

    def remove_position(self, msg_id: int) -> None:
        """Remove a dual position from tracking.

        Args:
            msg_id: The Telegram message ID to remove
        """
        dual = self.positions.pop(msg_id, None)
        if dual is not None:
            for pos in dual.all_positions:
                self.ticket_to_msg_id.pop(pos.mt5_ticket, None)

    def reassign_position(self, old_msg_id: int, new_msg_id: int) -> None:
        """Reassign a dual position to a new message ID.

        Used when a complete signal arrives after an incomplete one.

        Args:
            old_msg_id: The original message ID
            new_msg_id: The new message ID to assign to
        """
        dual = self.positions.pop(old_msg_id, None)
        if dual is not None:
            dual.telegram_msg_id = new_msg_id
            # Update all positions within the dual
            for pos in dual.all_positions:
                pos.telegram_msg_id = new_msg_id
                self.ticket_to_msg_id[pos.mt5_ticket] = new_msg_id
            self.positions[new_msg_id] = dual
            self.last_signal_msg_id = new_msg_id

    def _cleanup_old_records(self) -> None:
        """Keep only the last MAX_RECORDS positions (sorted by opened_at)."""
        if len(self.positions) <= self.MAX_RECORDS:
            return

        # Get the earliest opened_at from each DualPosition
        def get_earliest_opened(dual: DualPosition) -> datetime:
            positions = dual.all_positions
            if not positions:
                return datetime.min
            return min(p.opened_at for p in positions)

        sorted_duals = sorted(
            self.positions.items(),
            key=lambda x: get_earliest_opened(x[1]),
            reverse=True,
        )[: self.MAX_RECORDS]

        self.positions = dict(sorted_duals)

        # Rebuild ticket lookup
        self.ticket_to_msg_id = {}
        for msg_id, dual in self.positions.items():
            for pos in dual.all_positions:
                self.ticket_to_msg_id[pos.mt5_ticket] = msg_id

    def save(self) -> None:
        """Save state to JSON file (version 2 format) with automatic cleanup."""
        self._cleanup_old_records()

        data = {
            "version": self.CURRENT_VERSION,
            "last_updated": datetime.now().isoformat(),
            "last_signal_msg_id": self.last_signal_msg_id,
            "positions": {
                str(msg_id): dual.to_dict() for msg_id, dual in self.positions.items()
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

        Automatically migrates v1 format to v2/v3.
        v2 and v3 share the same format; v3 adds optional fields with defaults.
        If the file doesn't exist or is corrupted, starts with empty state.
        """
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            version = data.get("version", 1)
            self.last_signal_msg_id = data.get("last_signal_msg_id")

            if version == 1:
                self._migrate_v1_to_v2(data)
            else:
                # v2 and v3 use same format; v3 adds optional fields with defaults
                self._load_v2(data)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Warning: Error loading state file: {e}")
            # Start with empty state on error
            self.positions = {}
            self.ticket_to_msg_id = {}
            self.last_signal_msg_id = None

    def _migrate_v1_to_v2(self, data: dict) -> None:
        """Migrate version 1 state to version 2 dual-position format.

        V1 stored single TrackedPosition per msg_id.
        V2 stores DualPosition containing scalp/runner positions.
        """
        print("Migrating state file from v1 to v2...")

        for msg_id_str, pos_data in data.get("positions", {}).items():
            msg_id = int(msg_id_str)
            position = TrackedPosition.from_dict(pos_data)

            # Legacy positions become SINGLE (stored in scalp slot)
            position.role = TradeRole.SINGLE
            dual = DualPosition.from_single(position)
            self.positions[msg_id] = dual
            self.ticket_to_msg_id[position.mt5_ticket] = msg_id

        print(f"Migrated {len(self.positions)} positions to v2 format.")

    def _load_v2(self, data: dict) -> None:
        """Load version 2 state format."""
        for msg_id_str, dual_data in data.get("positions", {}).items():
            msg_id = int(msg_id_str)
            dual = DualPosition.from_dict(dual_data)
            self.positions[msg_id] = dual

            # Rebuild ticket lookup
            for pos in dual.all_positions:
                self.ticket_to_msg_id[pos.mt5_ticket] = msg_id

    def __len__(self) -> int:
        """Return the number of tracked dual positions."""
        return len(self.positions)

    def __contains__(self, msg_id: int) -> bool:
        """Check if a message ID is tracked."""
        return msg_id in self.positions
