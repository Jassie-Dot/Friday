from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from core.config import Settings

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LocalLLM(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        raise NotImplementedError


def _extract_json_blob(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if cleaned.startswith("{") or cleaned.startswith("["):
        return cleaned
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return match.group(1)


class OllamaClient(LocalLLM):
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.default_model = model or settings.primary_model
        self._client = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120.0)

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        normalized = [
            message.model_dump() if isinstance(message, ChatMessage) else ChatMessage.model_validate(message).model_dump()
            for message in messages
        ]
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": normalized,
            "stream": False,
            "options": {
                "temperature": self.settings.model_temperature if temperature is None else temperature,
            },
        }
        if response_format is not None:
            payload["format"] = response_format

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        raw_content = response.json()["message"]["content"]
        # Strip thinking tags from reasoning models
        cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
        return cleaned

    async def json_response(
        self,
        messages: list[ChatMessage | dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any] | list[Any]:
        raw = await self.chat(messages, model=model, temperature=temperature, response_format="json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Model returned non-JSON text; attempting extraction.")
            return json.loads(_extract_json_blob(raw))

    async def health(self) -> dict[str, Any]:
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
