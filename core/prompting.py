from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.models import utc_now


class PromptVariant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    notes: str = ""
    score: float = 0.5
    trials: int = 0
    successes: int = 0
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())
    last_used_at: str | None = None


class PromptProfile(BaseModel):
    key: str
    active_variant_id: str | None = None
    variants: list[PromptVariant] = Field(default_factory=list)


class PromptLibrary:
    def __init__(self, root: Path) -> None:
        self._path = root / "evolution" / "prompt-library.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._profiles: dict[str, PromptProfile] = {}
        self._load()

    def resolve(self, key: str, default_text: str) -> tuple[str, str]:
        with self._lock:
            profile = self._ensure_profile(key, default_text)
            variant = self._active_variant(profile)
            variant.last_used_at = utc_now().isoformat()
            self._save()
            return variant.text, variant.id

    def register_candidate(self, key: str, default_text: str, candidate_text: str, notes: str = "") -> PromptVariant:
        with self._lock:
            profile = self._ensure_profile(key, default_text)
            existing = next((item for item in profile.variants if item.text.strip() == candidate_text.strip()), None)
            if existing is not None:
                return existing
            candidate = PromptVariant(text=candidate_text, notes=notes)
            profile.variants.append(candidate)
            if profile.active_variant_id is None:
                profile.active_variant_id = candidate.id
            self._save()
            return candidate

    def record_outcome(self, key: str, default_text: str, variant_id: str, score: float, accepted: bool) -> None:
        with self._lock:
            profile = self._ensure_profile(key, default_text)
            variant = next((item for item in profile.variants if item.id == variant_id), None)
            if variant is None:
                return
            variant.trials += 1
            if accepted:
                variant.successes += 1
            variant.score = ((variant.score * (variant.trials - 1)) + score) / max(variant.trials, 1)
            best = max(profile.variants, key=lambda item: (item.score, item.successes, -item.trials))
            profile.active_variant_id = best.id
            self._save()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {key: profile.model_dump(mode="json") for key, profile in self._profiles.items()}

    def _ensure_profile(self, key: str, default_text: str) -> PromptProfile:
        profile = self._profiles.get(key)
        if profile is None:
            default_variant = PromptVariant(id="default", text=default_text, notes="Built-in system prompt.")
            profile = PromptProfile(key=key, active_variant_id=default_variant.id, variants=[default_variant])
            self._profiles[key] = profile
            return profile

        if not any(item.id == "default" for item in profile.variants):
            profile.variants.insert(0, PromptVariant(id="default", text=default_text, notes="Built-in system prompt."))
        default_variant = next(item for item in profile.variants if item.id == "default")
        default_variant.text = default_text
        if profile.active_variant_id is None:
            profile.active_variant_id = default_variant.id
        return profile

    def _active_variant(self, profile: PromptProfile) -> PromptVariant:
        if profile.active_variant_id:
            match = next((item for item in profile.variants if item.id == profile.active_variant_id), None)
            if match is not None:
                return match
        if not profile.variants:
            raise RuntimeError(f"Prompt profile '{profile.key}' has no variants.")
        profile.active_variant_id = profile.variants[0].id
        return profile.variants[0]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        for key, value in payload.items():
            try:
                self._profiles[key] = PromptProfile.model_validate(value)
            except Exception:
                continue

    def _save(self) -> None:
        payload = {key: profile.model_dump(mode="json") for key, profile in self._profiles.items()}
        self._path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
