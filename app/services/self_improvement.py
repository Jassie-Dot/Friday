from __future__ import annotations

import json
import logging

from app.llm.ollama import OllamaClient
from app.memory.store import MemoryStore
from app.schemas.tasks import TaskRecord

logger = logging.getLogger(__name__)


class SelfImprovementService:
    def __init__(self, llm: OllamaClient, memory: MemoryStore) -> None:
        self.llm = llm
        self.memory = memory

    async def analyze(self, task: TaskRecord) -> str:
        payload = {
            "objective": task.objective,
            "status": task.status.value,
            "summary": task.summary,
            "step_results": [result.model_dump(mode="json") for result in task.step_results],
        }
        fallback = self._heuristic_note(task)

        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You analyze completed autonomous tasks. Return JSON only with "
                            '{"learning_note":"..."} and focus on actionable improvements.'
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=self.llm.settings.fast_model,
            )
            note = result.get("learning_note", fallback) if isinstance(result, dict) else fallback
        except Exception as exc:
            logger.warning("Self-improvement fell back to heuristic: %s", exc)
            note = fallback

        self.memory.add(
            note,
            metadata={"type": "learning", "task_id": task.id, "status": task.status.value},
        )
        return note

    def _heuristic_note(self, task: TaskRecord) -> str:
        failures = [result for result in task.step_results if not result.success]
        if failures:
            return "Failures occurred. Narrow tool scope, inspect stderr, and prefer smaller retry steps."
        return "The task completed successfully. Reuse the same plan structure for similar objectives."
