from __future__ import annotations

import asyncio
import io
import logging
import tempfile
import wave
from pathlib import Path
from typing import Awaitable, Callable

from core.config import Settings

logger = logging.getLogger(__name__)


ChunkCallback = Callable[[bytes, int], Awaitable[None]]


class LocalVoiceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._whisper_model = None
        self._whisper_lock = asyncio.Lock()

    async def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int | None = None) -> dict[str, object]:
        if not pcm_bytes:
            return {"text": "", "language": "en", "duration_ms": 0}
        sample_rate = sample_rate or self.settings.voice_sample_rate
        return await asyncio.to_thread(self._transcribe_pcm_sync, pcm_bytes, sample_rate)

    async def stream_tts(
        self,
        text: str,
        on_chunk: ChunkCallback,
        cancel_event: asyncio.Event,
    ) -> dict[str, object]:
        if not text.strip():
            return {"sample_rate": self.settings.tts_sample_rate, "engine": "none", "characters": 0}
        if self.settings.piper_model_path:
            try:
                return await self._stream_with_piper(text, on_chunk, cancel_event)
            except Exception as exc:
                logger.warning("Piper streaming failed; falling back to pyttsx3: %s", exc)
        return await self._stream_with_pyttsx3(text, on_chunk, cancel_event)

    def _transcribe_pcm_sync(self, pcm_bytes: bytes, sample_rate: int) -> dict[str, object]:
        whisper = self._get_whisper_model_sync()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = Path(handle.name)
        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_bytes)

            segments, info = whisper.transcribe(
                str(wav_path),
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                word_timestamps=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            duration_ms = int((len(pcm_bytes) / 2) / sample_rate * 1000)
            return {"text": text, "language": getattr(info, "language", "en"), "duration_ms": duration_ms}
        finally:
            wav_path.unlink(missing_ok=True)

    def _get_whisper_model_sync(self):
        if self._whisper_model is not None:
            return self._whisper_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Voice dependencies are not installed. Install the voice extra.") from exc

        device = self.settings.whisper_device
        compute_type = self.settings.whisper_compute_type
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        self._whisper_model = WhisperModel(self.settings.whisper_model_size, device=device, compute_type=compute_type)
        return self._whisper_model

    async def _stream_with_piper(
        self,
        text: str,
        on_chunk: ChunkCallback,
        cancel_event: asyncio.Event,
    ) -> dict[str, object]:
        process = await asyncio.create_subprocess_exec(
            self.settings.piper_binary,
            "--model",
            self.settings.piper_model_path,
            "--output_raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdin is not None
        assert process.stdout is not None

        process.stdin.write(text.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()

        try:
            while not cancel_event.is_set():
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                await on_chunk(chunk, self.settings.tts_sample_rate)
        finally:
            if cancel_event.is_set() and process.returncode is None:
                process.kill()
            stderr = await process.stderr.read() if process.stderr is not None else b""
            returncode = await process.wait()
            if returncode != 0 and not cancel_event.is_set():
                raise RuntimeError(stderr.decode("utf-8", errors="replace").strip() or "Piper failed.")
        return {"sample_rate": self.settings.tts_sample_rate, "engine": "piper", "characters": len(text)}

    async def _stream_with_pyttsx3(
        self,
        text: str,
        on_chunk: ChunkCallback,
        cancel_event: asyncio.Event,
    ) -> dict[str, object]:
        wav_bytes = await asyncio.to_thread(self._render_pyttsx3_wav_sync, text)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            while not cancel_event.is_set():
                chunk = wav_file.readframes(2048)
                if not chunk:
                    break
                await on_chunk(chunk, sample_rate)
                await asyncio.sleep(0)
        return {"sample_rate": sample_rate, "engine": "pyttsx3", "characters": len(text)}

    @staticmethod
    def _render_pyttsx3_wav_sync(text: str) -> bytes:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("pyttsx3 is not installed. Install the voice extra.") from exc

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = Path(handle.name)
        try:
            engine = pyttsx3.init()
            engine.save_to_file(text, str(wav_path))
            engine.runAndWait()
            return wav_path.read_bytes()
        finally:
            wav_path.unlink(missing_ok=True)
