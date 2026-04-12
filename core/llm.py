from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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
    async def stream_chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
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


class _ReasoningCleaner:
    def __init__(self) -> None:
        self._buffer = ""
        self._visible = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        emitted = []
        while self._buffer:
            if self._in_think:
                end = self._buffer.find("</think>")
                if end == -1:
                    return ""
                self._buffer = self._buffer[end + len("</think>") :]
                self._in_think = False
                continue

            start = self._buffer.find("<think>")
            if start == -1:
                emitted.append(self._buffer)
                self._buffer = ""
                break
            if start > 0:
                emitted.append(self._buffer[:start])
            self._buffer = self._buffer[start + len("<think>") :]
            self._in_think = True

        visible = "".join(emitted)
        self._visible += visible
        return visible

    def finish(self) -> str:
        if self._in_think:
            return ""
        leftover = self._buffer
        self._buffer = ""
        self._visible += leftover
        return leftover


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
        normalized = self._normalize_messages(messages)
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
        return re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()

    async def stream_chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        normalized = self._normalize_messages(messages)
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": normalized,
            "stream": True,
            "options": {
                "temperature": self.settings.model_temperature if temperature is None else temperature,
            },
        }

        cleaner = _ReasoningCleaner()
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed Ollama stream line: %s", line[:120])
                    continue
                chunk = payload.get("message", {}).get("content", "")
                if chunk:
                    visible = cleaner.feed(chunk)
                    if visible:
                        yield visible
                if payload.get("done"):
                    tail = cleaner.finish()
                    if tail:
                        yield tail
                    break

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

    @staticmethod
    def _normalize_messages(messages: list[ChatMessage | dict[str, str]]) -> list[dict[str, str]]:
        return [
            message.model_dump() if isinstance(message, ChatMessage) else ChatMessage.model_validate(message).model_dump()
            for message in messages
        ]
