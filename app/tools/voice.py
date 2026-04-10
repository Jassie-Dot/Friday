from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.tools.base import BaseTool, ToolResult


class VoiceTool(BaseTool):
    name = "voice"
    description = "Performs local speech-to-text and text-to-speech."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _transcribe_sync(self, audio_path: Path) -> str:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Voice dependencies are not installed. Install the voice extra.") from exc

        model = WhisperModel(self.settings.whisper_model_size, device="cpu")
        segments, _info = model.transcribe(str(audio_path))
        return " ".join(segment.text.strip() for segment in segments)

    def _speak_sync(self, text: str, output_path: Path | None) -> str:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("pyttsx3 is not installed. Install the voice extra.") from exc

        engine = pyttsx3.init()
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            return str(output_path)

        engine.say(text)
        engine.runAndWait()
        return "Spoken through local system voice."

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "transcribe")

        if action == "transcribe":
            audio_path = kwargs.get("audio_path")
            if not audio_path:
                return ToolResult(success=False, output="Missing 'audio_path' argument.")
            transcript = await asyncio.to_thread(self._transcribe_sync, Path(audio_path))
            return ToolResult(success=True, output=transcript)

        if action == "speak":
            text = kwargs.get("text")
            if not text:
                return ToolResult(success=False, output="Missing 'text' argument.")
            output_path = kwargs.get("output_path")
            location = await asyncio.to_thread(
                self._speak_sync,
                text,
                Path(output_path) if output_path else None,
            )
            return ToolResult(success=True, output=location)

        return ToolResult(success=False, output=f"Unsupported voice action: {action}")
