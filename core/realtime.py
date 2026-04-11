from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from core.models import AgentEvent, FrontendMode, PresenceSnapshot

logger = logging.getLogger(__name__)


class ConversationEntry:
    """A single line in the conversation history."""
    __slots__ = ("role", "text", "timestamp")

    def __init__(self, role: str, text: str) -> None:
        self.role = role  # "user" or "friday"
        self.text = text
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "text": self.text, "timestamp": self.timestamp}


class RealtimeHub:
    """Broadcasts presence state and agent activity to realtime frontends."""

    def __init__(self, frontend_mode: FrontendMode) -> None:
        self._connections: set[WebSocket] = set()
        self._recent_events: deque[AgentEvent] = deque(maxlen=200)
        self._presence = PresenceSnapshot(frontend_mode=frontend_mode)
        self._conversation: deque[ConversationEntry] = deque(maxlen=50)

    @property
    def presence(self) -> PresenceSnapshot:
        return self._presence

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        await websocket.send_json(
            {
                "type": "bootstrap",
                "presence": self._presence.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in self._recent_events],
                "conversation": [entry.to_dict() for entry in self._conversation],
            }
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def record_event(self, event: AgentEvent) -> None:
        self._recent_events.append(event)
        await self._broadcast({"type": "event", "data": event.model_dump(mode="json")})

    async def set_presence(self, **updates: Any) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        self._presence = self._presence.model_copy(update=updates)
        await self._broadcast({"type": "presence", "data": self._presence.model_dump(mode="json")})

    async def add_conversation(self, role: str, text: str) -> None:
        """Add a line to the conversation log and push to all clients."""
        entry = ConversationEntry(role=role, text=text)
        self._conversation.append(entry)
        await self._broadcast({"type": "conversation", "data": entry.to_dict()})

    async def _broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(message)
            except Exception as exc:
                logger.warning("Dropping websocket client after send failure: %s", exc)
                stale.append(connection)
        for connection in stale:
            self._connections.discard(connection)

    def recent_events(self, limit: int = 50) -> list[AgentEvent]:
        return list(self._recent_events)[-limit:]
