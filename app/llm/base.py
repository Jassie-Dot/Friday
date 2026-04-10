from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LocalLLM(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        raise NotImplementedError
