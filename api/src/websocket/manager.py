"""WebSocket connection manager."""

import json
from datetime import datetime

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self.active_connections.discard(websocket)
        print(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Send a message to a specific client.

        Args:
            message: The message dict to send.
            websocket: The WebSocket connection to send to.
        """
        try:
            data = json.dumps(message, default=self._json_serializer)
            await websocket.send_text(data)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: The message dict to broadcast.
        """
        data = json.dumps(message, default=self._json_serializer)
        disconnected: set[WebSocket] = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.discard(conn)

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for objects not serializable by default."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()
