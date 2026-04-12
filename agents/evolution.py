from __future__ import annotations

import json
import logging

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName

logger = logging.getLogger(__name__)


class EvolutionAgent(BaseAgent):
    name = AgentName.evolution
    description = "Suggests prompt, routing, and architecture improvements based on task outcomes."

    SYSTEM_PROMPT = (
        "You improve FRIDAY's local runtime. Focus on measurable speed, reliability, and prompt quality gains. "
        'Return JSON only with {"prompt_key":"...","candidate_prompt":"...","summary":"...","suggested_upgrades":["..."]}. '
        "Use prompt_key values like chat.system or planner.system when proposing prompt changes. "
        "If no prompt change is needed, return an empty candidate_prompt string."
    )

    async def run(self, context: AgentContext) -> AgentResponse:
        prompt, _ = self.resolve_prompt("evolution.system", self.SYSTEM_PROMPT)
        fallback = {
            "prompt_key": "",
            "candidate_prompt": "",
            "summary": "Keep tracking latency, retries, and routing quality before changing active prompts.",
            "suggested_upgrades": ["Collect more voice-turn latency samples under live load."],
        }
        try:
            result = await self.llm.json_response(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "objective": context.objective,
                                "task_context": context.task_context,
                                "previous_results": [item.model_dump(mode="json") for item in context.previous_results[-8:]],
                                "failure_reason": context.failure_reason,
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
                model=self.llm.settings.primary_model,
            )
            if not isinstance(result, dict):
                result = fallback
        except Exception as exc:
            logger.warning("Evolution agent fell back to heuristic result: %s", exc)
            result = fallback

        return AgentResponse(
            success=True,
            summary=result.get("summary", fallback["summary"]),
            data=result,
            memory_entries=[
                {
                    "document": f"Evolution note for '{context.objective}': {json.dumps(result, ensure_ascii=True)}",
                    "metadata": {"agent": self.name.value, "type": "evolution"},
                }
            ],
        )
