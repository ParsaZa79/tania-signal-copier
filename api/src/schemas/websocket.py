"""WebSocket message schemas."""

from datetime import datetime

from pydantic import BaseModel

from .account import AccountInfo
from .position import PositionResponse


class WebSocketMessage(BaseModel):
    """Base WebSocket message."""

    type: str
    timestamp: datetime


class UpdateMessage(WebSocketMessage):
    """Real-time update message with positions and account info."""

    type: str = "update"
    positions: list[PositionResponse] = []
    account: AccountInfo | None = None


class ErrorMessage(WebSocketMessage):
    """Error message."""

    type: str = "error"
    error: str
    code: int | None = None
