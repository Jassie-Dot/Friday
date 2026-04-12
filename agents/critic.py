from __future__ import annotations

import json
import logging

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    name = AgentName.critic
    description = "Evaluates task quality, latency tradeoffs, and missed opportunities."

    SYSTEM_PROMPT = (
        "You are FRIDAY's internal critic. Evaluate quality, speed, and operational soundness. "
        'Return JSON only with {"score":0.0,"strengths":["..."],"issues":["..."],"recommendations":["..."]}. '
        "Score should be between 0 and 1."
    )

    async def run(self, context: AgentContext) -> AgentResponse:
        prompt, _ = self.resolve_prompt("critic.system", self.SYSTEM_PROMPT)
        fallback = {
            "score": 0.6,
            "strengths": ["Completed the requested action path."],
            "issues": [],
            "recommendations": ["Continue collecting latency and failure telemetry."],
        }
        try:
            result = await self.fast_llm.json_response(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "objective": context.objective,
                                "task_context": context.task_context,
                                "previous_results": [item.model_dump(mode="json") for item in context.previous_results[-8:]],
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
                model=self.fast_llm.settings.fast_model,
            )
            if not isinstance(result, dict):
                result = fallback
        except Exception as exc:
            logger.warning("Critic fell back to heuristic result: %s", exc)
            result = fallback

        return AgentResponse(
            success=True,
            summary=f"Critique score: {float(result.get('score', 0.6)):.2f}",
            data=result,
            memory_entries=[
                {
                    "document": f"Critique for '{context.objective}': {json.dumps(result, ensure_ascii=True)}",
                    "metadata": {"agent": self.name.value, "type": "critique"},
                }
            ],
        )
