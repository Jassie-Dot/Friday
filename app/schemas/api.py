from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5
    where: dict[str, Any] | None = None


class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    init_image_path: Path | None = None
    output_path: Path | None = None
    batch_size: int = 1
    steps: int = 30
    guidance_scale: float = 7.5


class VoiceTranscriptionRequest(BaseModel):
    audio_path: Path


class SpeechRequest(BaseModel):
    text: str
    output_path: Path | None = None


class ApiEnvelope(BaseModel):
    ok: bool = True
    data: Any = Field(default_factory=dict)
    message: str = "success"
