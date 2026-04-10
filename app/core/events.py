from __future__ import annotations

from collections import deque
from typing import Awaitable, Callable

from app.schemas.tasks import AgentMessage


Subscriber = Callable[[AgentMessage], Awaitable[None] | None]


class EventBus:
    def __init__(self, max_events: int = 500) -> None:
        self._subscribers: list[Subscriber] = []
        self._events: deque[AgentMessage] = deque(maxlen=max_events)

    async def publish(self, event: AgentMessage) -> None:
        self._events.append(event)
        for subscriber in list(self._subscribers):
            result = subscriber(event)
            if result is not None and hasattr(result, "__await__"):
                await result

    def subscribe(self, callback: Subscriber) -> None:
        self._subscribers.append(callback)

    def recent(self, limit: int = 50) -> list[AgentMessage]:
        return list(self._events)[-limit:]
