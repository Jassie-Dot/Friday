from __future__ import annotations

import asyncio
import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Awaitable, Callable

from core.config import Settings
from core.llm import OllamaClient
from core.prompting import PromptLibrary
from core.realtime import RealtimeHub
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, dict[str, object]], Awaitable[None]]


class HybridIntelligenceService:
    SYSTEM_PROMPT = (
        "You are FRIDAY, a real-time voice intelligence. Respond with concise spoken-language answers. "
        "Prioritize clarity, confidence, and fast comprehension. Avoid markdown, bullet formatting, and long preambles. "
        "If the user asks for work that requires longer execution, acknowledge briefly and let the execution layer handle depth."
    )

    def __init__(
        self,
        settings: Settings,
        llm: OllamaClient,
        fast_llm: OllamaClient,
        memory: MemoryStore,
        prompts: PromptLibrary,
        realtime: RealtimeHub,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.fast_llm = fast_llm
        self.memory = memory
        self.prompts = prompts
        self.realtime = realtime
        self._cache_path = settings.cache_dir / "intelligence-cache.json"
        self._cache_lock = asyncio.Lock()
        self._cache = self._load_cache()

    async def stream_response(
        self,
        *,
        objective: str,
        conversation_history: list[dict[str, str]],
        emit: EmitCallback,
        cancel_event: asyncio.Event,
        route_hint: str = "auto",
    ) -> dict[str, object]:
        started = perf_counter()
        system_prompt, prompt_variant_id = self.prompts.resolve("intelligence.system", self.SYSTEM_PROMPT)
        memories = self.memory.query(objective, limit=4)
        messages = self._build_messages(system_prompt, objective, conversation_history, memories)
        cache_key = self._cache_key(objective, conversation_history)
        cached = await self._cache_get(cache_key)
        if cached:
            first_response_ms = (perf_counter() - started) * 1000
            await emit(
                "assistant.start",
                {
                    "route": "cache",
                    "model": self.settings.fast_model,
                    "cache_hit": True,
                    "prompt_variant_id": prompt_variant_id,
                },
            )
            text = str(cached.get("response", ""))
            await self._emit_cached(text, emit)
            return {
                "text": text,
                "first_response_ms": first_response_ms,
                "cache_hit": True,
                "model": self.settings.fast_model,
                "prompt_variant_id": prompt_variant_id,
            }

        await emit(
            "assistant.start",
            {
                "route": "fast-smart",
                "model": self.settings.fast_model,
                "cache_hit": False,
                "prompt_variant_id": prompt_variant_id,
            },
        )

        smart_task: asyncio.Task[str] | None = None
        if route_hint != "fast-only" and self.settings.primary_model != self.settings.fast_model:
            smart_task = asyncio.create_task(self.llm.chat(messages, model=self.settings.primary_model))

        fast_text = ""
        segment_buffer = ""
        first_response_ms = 0.0

        async for chunk in self.fast_llm.stream_chat(messages, model=self.settings.fast_model):
            if cancel_event.is_set():
                break
            if not first_response_ms:
                first_response_ms = (perf_counter() - started) * 1000
            fast_text += chunk
            segment_buffer += chunk
            await emit("assistant.token", {"delta": chunk, "text": fast_text})
            segments, segment_buffer = self._drain_segments(segment_buffer)
            for segment in segments:
                await emit("assistant.segment", {"text": segment, "final": False})

        if cancel_event.is_set():
            return {
                "text": fast_text.strip(),
                "first_response_ms": first_response_ms,
                "cache_hit": False,
                "model": self.settings.fast_model,
                "prompt_variant_id": prompt_variant_id,
                "interrupted": True,
            }

        final_text = fast_text.strip()
        if segment_buffer.strip():
            segment_text = segment_buffer.strip()
            await emit("assistant.segment", {"text": segment_text, "final": False})

        if not final_text:
            final_text = "I'm still on the signal, Boss, but that response came back empty."

        await emit(
            "assistant.final",
            {
                "text": final_text,
                "model": self.settings.fast_model,
                "first_response_ms": first_response_ms,
            },
        )
        await self._cache_put(cache_key, {"response": final_text, "model": self.settings.fast_model})

        if smart_task is not None:
            asyncio.create_task(
                self._watch_refinement(
                    objective=objective,
                    fast_text=final_text,
                    smart_task=smart_task,
                    emit=emit,
                    cancel_event=cancel_event,
                    cache_key=cache_key,
                )
            )

        self.memory.add(
            f"Voice turn: {objective}\nFRIDAY: {final_text}",
            {"type": "voice_turn", "model": self.settings.fast_model},
        )
        return {
            "text": final_text,
            "first_response_ms": first_response_ms,
            "cache_hit": False,
            "model": self.settings.fast_model,
            "prompt_variant_id": prompt_variant_id,
        }

    async def acknowledge_task(self, objective: str, emit: EmitCallback) -> str:
        acknowledgement = self._acknowledgement_for(objective)
        await emit(
            "assistant.final",
            {
                "text": acknowledgement,
                "model": self.settings.fast_model,
                "first_response_ms": 0.0,
                "task_ack": True,
            },
        )
        return acknowledgement

    def _build_messages(
        self,
        system_prompt: str,
        objective: str,
        conversation_history: list[dict[str, str]],
        memories,
    ) -> list[dict[str, str]]:
        memory_lines = "\n".join(f"- {memory.document[:220]}" for memory in memories[:4])
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in conversation_history[-8:]:
            role = item.get("role", "assistant")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": item.get("content", "")[:1200]})
        if memory_lines:
            messages.append({"role": "system", "content": f"Relevant memory:\n{memory_lines}"})
        messages.append({"role": "user", "content": objective})
        return messages

    async def _watch_refinement(
        self,
        *,
        objective: str,
        fast_text: str,
        smart_task: asyncio.Task[str],
        emit: EmitCallback,
        cancel_event: asyncio.Event,
        cache_key: str,
    ) -> None:
        try:
            timeout = self.settings.speculative_refinement_window_ms / 1000
            smart_text = await asyncio.wait_for(asyncio.shield(smart_task), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                smart_text = await smart_task
            except Exception as exc:
                logger.debug("Primary-model refinement failed after timeout: %s", exc)
                return
        except Exception as exc:
            logger.debug("Primary-model refinement failed: %s", exc)
            return

        if cancel_event.is_set():
            return
        candidate = smart_text.strip()
        if not candidate:
            return
        similarity = SequenceMatcher(a=fast_text, b=candidate).ratio()
        if similarity >= 0.92:
            await self._cache_put(cache_key, {"response": fast_text, "model": self.settings.primary_model})
            return

        refinement = self._condense_refinement(fast_text, candidate)
        await emit(
            "assistant.refinement",
            {
                "text": refinement,
                "full_text": candidate,
                "model": self.settings.primary_model,
                "objective": objective,
            },
        )
        await self._cache_put(cache_key, {"response": candidate, "model": self.settings.primary_model})
        self.memory.add(
            f"Refined answer for '{objective}': {candidate}",
            {"type": "voice_refinement", "model": self.settings.primary_model},
        )

    async def _emit_cached(self, text: str, emit: EmitCallback) -> None:
        assembled = ""
        segment_buffer = ""
        for chunk in re.findall(r".{1,48}(?:\s+|$)", text) or [text]:
            assembled += chunk
            segment_buffer += chunk
            await emit("assistant.token", {"delta": chunk, "text": assembled})
            segments, segment_buffer = self._drain_segments(segment_buffer)
            for segment in segments:
                await emit("assistant.segment", {"text": segment, "final": False})
        if segment_buffer.strip():
            await emit("assistant.segment", {"text": segment_buffer.strip(), "final": False})
        await emit("assistant.final", {"text": text, "model": self.settings.fast_model, "cache_hit": True})

    @staticmethod
    def _drain_segments(buffer: str) -> tuple[list[str], str]:
        matches = list(re.finditer(r"(.+?[.!?]+)(?:\s+|$)", buffer, flags=re.DOTALL))
        if not matches:
            if len(buffer) > 180:
                cut = buffer.rfind(" ", 0, 180)
                cut = cut if cut > 40 else 180
                return [buffer[:cut].strip()], buffer[cut:].lstrip()
            return [], buffer
        last_end = matches[-1].end()
        segments = [match.group(1).strip() for match in matches if match.group(1).strip()]
        return segments, buffer[last_end:].lstrip()

    @staticmethod
    def _condense_refinement(fast_text: str, smart_text: str) -> str:
        if len(smart_text) <= len(fast_text) + 20:
            return smart_text
        first_sentence = re.split(r"(?<=[.!?])\s+", smart_text.strip(), maxsplit=1)[0]
        return f"One refinement, Boss: {first_sentence}"

    @staticmethod
    def _acknowledgement_for(objective: str) -> str:
        lowered = objective.lower()
        if any(token in lowered for token in ("build", "code", "refactor", "fix", "run")):
            return "Understood. Spinning up the execution stack now."
        if any(token in lowered for token in ("search", "research", "investigate", "compare")):
            return "Understood. I am pulling the relevant signals together now."
        return "Understood. Running that through active protocols now."

    @staticmethod
    def _cache_key(objective: str, history: list[dict[str, str]]) -> str:
        history_key = " | ".join(f"{item.get('role', '')}:{item.get('content', '')[:120]}" for item in history[-4:])
        return f"{objective.strip().lower()}::{history_key.strip().lower()}"

    def _load_cache(self) -> dict[str, dict[str, object]]:
        if not self._cache_path.exists():
            return {}
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    async def _cache_get(self, key: str) -> dict[str, object] | None:
        async with self._cache_lock:
            value = self._cache.get(key)
            if not value:
                return None
            return value

    async def _cache_put(self, key: str, value: dict[str, object]) -> None:
        async with self._cache_lock:
            self._cache[key] = value
            # Keep the cache bounded without adding another dependency.
            if len(self._cache) > 300:
                overflow = len(self._cache) - 300
                for stale_key in list(self._cache.keys())[:overflow]:
                    self._cache.pop(stale_key, None)
            self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=True, indent=2), encoding="utf-8")
