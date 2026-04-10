from __future__ import annotations

from collections import deque
from typing import Awaitable, Callable

from core.models import AgentEvent


Subscriber = Callable[[AgentEvent], Awaitable[None] | None]


class EventBus:
    def __init__(self, max_events: int = 500) -> None:
        self._events: deque[AgentEvent] = deque(maxlen=max_events)
        self._subscribers: list[Subscriber] = []

    async def publish(self, event: AgentEvent) -> None:
        self._events.append(event)
        for subscriber in list(self._subscribers):
            result = subscriber(event)
            if result is not None and hasattr(result, "__await__"):
                await result

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def recent(self, limit: int = 50) -> list[AgentEvent]:
        return list(self._events)[-limit:]
