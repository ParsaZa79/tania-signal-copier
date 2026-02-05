"""WebSocket log streaming manager for bot output."""

import json
from datetime import datetime

from fastapi import WebSocket


class LogManager:
    """Manages WebSocket connections for streaming bot logs."""

    def __init__(self):
        """Initialize the log manager."""
        self.connections: set[WebSocket] = set()
        self.log_buffer: list[dict] = []  # Keep last 100 logs
        self.max_buffer_size = 100

    async def connect(self, websocket: WebSocket) -> bool:
        """Accept and register a new WebSocket connection.

        Sends buffered logs to new client.

        Returns:
            True if connection was successful, False if it failed.
        """
        try:
            await websocket.accept()
            self.connections.add(websocket)
            print(f"Log WebSocket connected. Total connections: {len(self.connections)}")

            # Send buffered logs to new client (or empty history to confirm connection)
            await websocket.send_text(
                json.dumps({
                    "type": "history",
                    "logs": self.log_buffer,
                })
            )
            return True
        except Exception as e:
            print(f"Log WebSocket connection failed: {e}")
            self.connections.discard(websocket)
            return False

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(websocket)
        print(f"Log WebSocket disconnected. Total connections: {len(self.connections)}")

    async def broadcast_log(self, message: str, level: str = "info") -> None:
        """Broadcast a log message to all connected clients.

        Args:
            message: The log message text.
            level: Log level (info, warning, error, bot).
        """
        log_entry = {
            "id": f"{datetime.now().timestamp()}-{id(message)}",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
        }

        # Add to buffer
        self.log_buffer.append(log_entry)
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size :]

        # Broadcast to all connections
        data = json.dumps({
            "type": "log",
            "log": log_entry,
        })

        disconnected: set[WebSocket] = set()

        for connection in self.connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                print(f"Error sending log to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.connections.discard(conn)

    def clear_buffer(self) -> None:
        """Clear the log buffer."""
        self.log_buffer.clear()

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.connections)


# Global log manager instance
log_manager = LogManager()
