from __future__ import annotations

import logging
from typing import Any

from core.models import EvolutionNote, TaskCritique, TaskRecord
from core.prompting import PromptLibrary
from memory.store import MemoryStore

logger = logging.getLogger(__name__)


class RuntimeEvolutionService:
    def __init__(self, prompts: PromptLibrary, memory: MemoryStore, prompt_defaults: dict[str, str]) -> None:
        self.prompts = prompts
        self.memory = memory
        self.prompt_defaults = prompt_defaults

    def apply(self, record: TaskRecord, critique: TaskCritique | None, proposal: dict[str, Any] | None) -> EvolutionNote:
        proposal = proposal or {}
        prompt_key = str(proposal.get("prompt_key", "")).strip() or None
        candidate_prompt = str(proposal.get("candidate_prompt", "")).strip()
        summary = str(proposal.get("summary", "")).strip() or "No prompt changes were promoted for this task."
        suggested_upgrades = [str(item).strip() for item in proposal.get("suggested_upgrades", []) if str(item).strip()]
        variant_id = None

        if prompt_key and candidate_prompt and prompt_key in self.prompt_defaults:
            candidate = self.prompts.register_candidate(
                prompt_key,
                self.prompt_defaults[prompt_key],
                candidate_prompt,
                notes=f"Derived from task {record.id}",
            )
            variant_id = candidate.id
            if critique is not None:
                self.prompts.record_outcome(
                    prompt_key,
                    self.prompt_defaults[prompt_key],
                    candidate.id,
                    critique.score,
                    critique.score >= 0.7,
                )

        if critique is not None:
            self.memory.add(
                f"Evolution summary for '{record.objective}': {summary}",
                {
                    "type": "evolution_summary",
                    "task_id": record.id,
                    "score": critique.score,
                    "prompt_key": prompt_key,
                    "variant_id": variant_id,
                },
            )

        return EvolutionNote(
            prompt_key=prompt_key,
            variant_id=variant_id,
            summary=summary,
            suggested_upgrades=suggested_upgrades,
        )
