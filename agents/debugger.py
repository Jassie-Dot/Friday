from __future__ import annotations

import json
import logging

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName

logger = logging.getLogger(__name__)


class DebugAgent(BaseAgent):
    name = AgentName.debug
    description = "Analyzes failed steps and proposes safe retries."

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "debug_started", {"failure": context.failure_reason or "unknown"})
        fallback = {
            "root_cause": context.failure_reason or "Unknown failure",
            "summary": "Inspect stderr, narrow scope, and retry with a smaller action.",
            "suggested_retry_inputs": {},
        }
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You diagnose local autonomous task failures. Return JSON only with "
                            '{"root_cause":"...", "summary":"...", "suggested_retry_inputs":{}}. '
                            "Only suggest minimal safe retries."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "objective": context.objective,
                                "step": context.step.model_dump() if context.step else None,
                                "failure": context.failure_reason,
                                "previous_results": [item.model_dump(mode="json") for item in context.previous_results[-3:]],
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
                model=self.llm.settings.fast_model,
            )
            if not isinstance(result, dict):
                result = fallback
        except Exception as exc:
            logger.warning("Debug agent fell back to heuristic result: %s", exc)
            result = fallback
        await self.emit(context.task_id, "debug_finished", {"summary": result.get("summary", "")})
        return AgentResponse(
            success=True,
            summary=result.get("summary", fallback["summary"]),
            data=result,
            memory_entries=[
                {
                    "document": f"Failure analysis for '{context.objective}': {result.get('summary', fallback['summary'])}",
                    "metadata": {"agent": self.name.value, "type": "debug"},
                }
            ],
        )
