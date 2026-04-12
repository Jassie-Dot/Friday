from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from core.config import Settings
from core.intent import is_conversational
from core.intelligence import HybridIntelligenceService
from core.models import ObjectiveRequest, PresenceMode
from core.realtime import RealtimeHub
from core.voice_engine import LocalVoiceEngine

logger = logging.getLogger(__name__)


@dataclass
class SpeechEnvelope:
    speech_id: str
    text: str
    priority: str = "normal"


@dataclass
class VoiceSession:
    id: str
    websocket: WebSocket
    audio_buffer: bytearray = field(default_factory=bytearray)
    sample_rate: int = 16000
    conversation: list[dict[str, str]] = field(default_factory=list)
    speech_queue: asyncio.Queue[SpeechEnvelope | None] = field(default_factory=asyncio.Queue)
    speech_worker: asyncio.Task[None] | None = None
    response_task: asyncio.Task[None] | None = None
    task_worker: asyncio.Task[None] | None = None
    partial_task: asyncio.Task[None] | None = None
    generation_cancel: asyncio.Event = field(default_factory=asyncio.Event)
    speech_cancel: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    transcription_revision: int = 0
    active: bool = True
    speaking: bool = False
    segment_count: int = 0
    pending_final_text: str = ""
    interruptions: int = 0
    turn_revision: int = 0


class VoiceSessionManager:
    def __init__(
        self,
        *,
        settings: Settings,
        realtime: RealtimeHub,
        voice: LocalVoiceEngine,
        intelligence: HybridIntelligenceService,
        orchestrator,
    ) -> None:
        self.settings = settings
        self.realtime = realtime
        self.voice = voice
        self.intelligence = intelligence
        self.orchestrator = orchestrator
        self._sessions: dict[str, VoiceSession] = {}

    async def connect(self, websocket: WebSocket) -> VoiceSession:
        await websocket.accept()
        session = VoiceSession(id=str(uuid4()), websocket=websocket, sample_rate=self.settings.voice_sample_rate)
        session.speech_worker = asyncio.create_task(self._speech_worker(session))
        self._sessions[session.id] = session
        await self._send(
            session,
            {
                "type": "session.ready",
                "session_id": session.id,
                "sample_rate": self.settings.voice_sample_rate,
                "tts_sample_rate": self.settings.tts_sample_rate,
            },
        )
        await self.realtime.set_presence(
            mode=PresenceMode.idle,
            headline="FRIDAY",
            whisper="Voice link armed",
            active_agents=[],
            current_objective=None,
            energy=0.18,
        )
        return session

    async def disconnect(self, session: VoiceSession) -> None:
        session.active = False
        await self._interrupt(session, reason="disconnect", cancel_response=True, cancel_task_worker=True)
        if session.partial_task and not session.partial_task.done():
            session.partial_task.cancel()
        if session.speech_worker:
            await session.speech_queue.put(None)
            try:
                await session.speech_worker
            except Exception:
                pass
        self._sessions.pop(session.id, None)

    async def handle_message(self, session: VoiceSession, payload: dict[str, Any]) -> None:
        message_type = payload.get("type")
        if message_type == "audio.frame":
            await self._handle_audio_frame(session, payload)
            return
        if message_type == "audio.commit":
            await self._commit_audio(session)
            return
        if message_type == "interrupt":
            await self._interrupt(session, reason="client_interrupt", cancel_response=True, cancel_task_worker=False)
            return
        if message_type == "objective":
            text = str(payload.get("text", "")).strip()
            if text:
                await self._dispatch_objective(session, text)
            return
        if message_type == "ping":
            await self._send(session, {"type": "pong"})

    async def _handle_audio_frame(self, session: VoiceSession, payload: dict[str, Any]) -> None:
        audio_b64 = payload.get("audio")
        if not audio_b64:
            return
        pcm_bytes = base64.b64decode(audio_b64)
        if not pcm_bytes:
            return
        session.sample_rate = int(payload.get("sample_rate") or self.settings.voice_sample_rate)

        if session.speaking or (session.response_task and not session.response_task.done()):
            await self._interrupt(session, reason="barge_in", cancel_response=True, cancel_task_worker=False)

        session.audio_buffer.extend(pcm_bytes)
        await self.realtime.set_presence(
            mode=PresenceMode.listening,
            headline="Listening",
            whisper="Incoming voice signal",
            active_agents=[],
            current_objective=None,
            energy=min(0.32 + float(payload.get("rms", 0.0)), 0.75),
        )
        await self._schedule_partial_transcript(session)

    async def _schedule_partial_transcript(self, session: VoiceSession) -> None:
        if session.partial_task and not session.partial_task.done():
            return
        window_frames = int(session.sample_rate * (self.settings.partial_transcription_window_ms / 1000))
        window_bytes = max(window_frames * 2, 3200)
        if len(session.audio_buffer) < window_bytes:
            return
        session.transcription_revision += 1
        revision = session.transcription_revision
        snapshot = bytes(session.audio_buffer[-window_bytes:])
        session.partial_task = asyncio.create_task(self._emit_partial_transcript(session, snapshot, revision))

    async def _emit_partial_transcript(self, session: VoiceSession, pcm_snapshot: bytes, revision: int) -> None:
        try:
            result = await self.voice.transcribe_pcm(pcm_snapshot, session.sample_rate)
        except Exception as exc:
            logger.debug("Partial transcription failed: %s", exc)
            return
        text = str(result.get("text", "")).strip()
        if not text or revision != session.transcription_revision or not session.active:
            return
        await self._send(session, {"type": "transcript.partial", "text": text})

    async def _commit_audio(self, session: VoiceSession) -> None:
        if not session.audio_buffer:
            return
        pcm_bytes = bytes(session.audio_buffer)
        session.audio_buffer.clear()
        session.transcription_revision += 1
        started = perf_counter()
        try:
            result = await self.voice.transcribe_pcm(pcm_bytes, session.sample_rate)
        except Exception as exc:
            await self._send(session, {"type": "transcript.error", "message": str(exc)})
            return
        text = str(result.get("text", "")).strip()
        if not text:
            await self._send(session, {"type": "transcript.empty"})
            await self.realtime.set_presence(
                mode=PresenceMode.idle,
                headline="FRIDAY",
                whisper="Standing by",
                active_agents=[],
                current_objective=None,
                energy=0.16,
            )
            return

        session.conversation.append({"role": "user", "content": text})
        await self._send(
            session,
            {
                "type": "transcript.final",
                "text": text,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        await self._dispatch_objective(session, text)

    async def _dispatch_objective(self, session: VoiceSession, text: str) -> None:
        await self._interrupt(session, reason="new_turn", cancel_response=True, cancel_task_worker=False)
        session.generation_cancel = asyncio.Event()
        session.segment_count = 0
        session.pending_final_text = ""
        session.turn_revision += 1
        revision = session.turn_revision

        if is_conversational(text):
            await self.realtime.add_conversation(role="user", text=text)
            session.response_task = asyncio.create_task(self._run_conversational_turn(session, text, revision))
            return

        session.task_worker = asyncio.create_task(self._run_task_turn(session, text, revision))

    async def _run_conversational_turn(self, session: VoiceSession, text: str, revision: int) -> None:
        await self.realtime.set_presence(
            mode=PresenceMode.thinking,
            headline="Thinking",
            whisper=text,
            active_agents=[],
            current_objective=text,
            energy=0.52,
        )

        async def emit(event_type: str, payload: dict[str, object]) -> None:
            if revision != session.turn_revision:
                return
            await self._send(session, {"type": event_type, **payload})
            if event_type == "assistant.segment":
                segment = str(payload.get("text", "")).strip()
                if segment:
                    session.segment_count += 1
                    await session.speech_queue.put(SpeechEnvelope(speech_id=str(uuid4()), text=segment))
            elif event_type == "assistant.refinement":
                refinement = str(payload.get("text", "")).strip()
                if refinement:
                    await session.speech_queue.put(SpeechEnvelope(speech_id=str(uuid4()), text=refinement, priority="high"))
            elif event_type == "assistant.final":
                session.pending_final_text = str(payload.get("text", "")).strip()

        result = await self.intelligence.stream_response(
            objective=text,
            conversation_history=session.conversation[:-1],
            emit=emit,
            cancel_event=session.generation_cancel,
        )
        if revision != session.turn_revision:
            return
        final_text = str(result.get("text", "")).strip()
        if not final_text or session.generation_cancel.is_set():
            return
        session.conversation.append({"role": "assistant", "content": final_text})
        await self.realtime.add_conversation(role="friday", text=final_text)
        if session.segment_count == 0:
            await session.speech_queue.put(SpeechEnvelope(speech_id=str(uuid4()), text=final_text))

    async def _run_task_turn(self, session: VoiceSession, text: str, revision: int) -> None:
        await self.realtime.set_presence(
            mode=PresenceMode.executing,
            headline="Executing",
            whisper=text,
            active_agents=[],
            current_objective=text,
            energy=0.72,
        )

        async def emit(event_type: str, payload: dict[str, object]) -> None:
            if revision != session.turn_revision:
                return
            await self._send(session, {"type": event_type, **payload})
            if event_type == "assistant.final":
                ack_text = str(payload.get("text", "")).strip()
                if ack_text:
                    await session.speech_queue.put(SpeechEnvelope(speech_id=str(uuid4()), text=ack_text))

        await self.intelligence.acknowledge_task(text, emit)
        record = await self.orchestrator.run(
            ObjectiveRequest(objective=text, context={"source": "voice-session", "session_id": session.id})
        )
        if revision != session.turn_revision:
            return
        final_text = record.summary or "Objective complete."
        session.conversation.append({"role": "assistant", "content": final_text})
        await self._send(session, {"type": "assistant.task_complete", "task_id": record.id, "text": final_text})
        await session.speech_queue.put(SpeechEnvelope(speech_id=str(uuid4()), text=final_text, priority="high"))

    async def _speech_worker(self, session: VoiceSession) -> None:
        while True:
            envelope = await session.speech_queue.get()
            if envelope is None:
                session.speech_queue.task_done()
                return
            session.speech_cancel = asyncio.Event()
            session.speaking = True
            try:
                await self.realtime.set_presence(
                    mode=PresenceMode.speaking,
                    headline="Speaking",
                    whisper=envelope.text[:100],
                    active_agents=[],
                    current_objective=None,
                    energy=0.64,
                )
                await self._send(session, {"type": "voice.start", "speech_id": envelope.speech_id, "text": envelope.text})

                async def on_chunk(chunk: bytes, sample_rate: int) -> None:
                    await self._send(
                        session,
                        {
                            "type": "voice.chunk",
                            "speech_id": envelope.speech_id,
                            "audio": base64.b64encode(chunk).decode("ascii"),
                            "sample_rate": sample_rate,
                            "format": "pcm_s16le",
                        },
                    )

                await self.voice.stream_tts(envelope.text, on_chunk, session.speech_cancel)
                if session.speech_cancel.is_set():
                    await self._send(session, {"type": "voice.interrupt", "speech_id": envelope.speech_id})
                else:
                    await self._send(session, {"type": "voice.end", "speech_id": envelope.speech_id})
            except Exception as exc:
                logger.warning("Speech worker failed: %s", exc)
                await self._send(session, {"type": "voice.error", "message": str(exc)})
            finally:
                session.speaking = False
                session.speech_queue.task_done()
                if session.speech_queue.empty() and not self._is_busy(session):
                    await self.realtime.set_presence(
                        mode=PresenceMode.idle,
                        headline="FRIDAY",
                        whisper="Standing by",
                        active_agents=[],
                        current_objective=None,
                        energy=0.16,
                    )

    async def _interrupt(
        self,
        session: VoiceSession,
        *,
        reason: str,
        cancel_response: bool,
        cancel_task_worker: bool,
    ) -> None:
        was_busy = self._is_busy(session)
        session.generation_cancel.set()
        session.speech_cancel.set()

        if cancel_response and session.response_task and not session.response_task.done():
            session.response_task.cancel()
        if cancel_task_worker and session.task_worker and not session.task_worker.done():
            session.task_worker.cancel()

        while not session.speech_queue.empty():
            try:
                item = session.speech_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is not None:
                session.speech_queue.task_done()

        if was_busy:
            session.interruptions += 1
            await self._send(session, {"type": "voice.interrupt", "reason": reason, "interruptions": session.interruptions})
            await self.realtime.set_presence(
                mode=PresenceMode.listening,
                headline="Listening",
                whisper="Barge-in detected",
                active_agents=[],
                current_objective=None,
                energy=0.44,
            )

    async def _send(self, session: VoiceSession, message: dict[str, object]) -> None:
        if not session.active:
            return
        async with session.send_lock:
            await session.websocket.send_json(message)

    @staticmethod
    def _is_busy(session: VoiceSession) -> bool:
        response_running = session.response_task is not None and not session.response_task.done()
        task_running = session.task_worker is not None and not session.task_worker.done()
        speaking = session.speaking or not session.speech_queue.empty()
        return response_running or task_running or speaking
