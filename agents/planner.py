from __future__ import annotations

import json
import logging

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName, TaskPlan, TaskStep

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    name = AgentName.planner
    description = "Breaks objectives into structured steps for specialist agents."

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "planning_started", {"objective": context.objective})
        payload = {
            "objective": context.objective,
            "context": context.task_context,
            "memories": [memory.model_dump() for memory in context.memories[:5]],
            "available_agents": [
                {"name": "executor", "best_for": "code execution, shell, files, python"},
                {"name": "web", "best_for": "internet search, scraping, summarization"},
                {"name": "vision", "best_for": "image generation and editing"},
                {"name": "voice", "best_for": "speech to text and text to speech"},
                {"name": "system", "best_for": "browser control, os actions, automation"},
            ],
        }
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are the planner for FRIDAY. Return JSON only with "
                            '{"reasoning":"...", "steps":[{"title":"...", "agent":"executor|web|vision|voice|system", '
                            '"goal":"...", "inputs":{}, "expected_output":"..."}]}. '
                            "Keep the plan concrete, safe, and under 8 steps."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=self.llm.settings.fast_model,
            )
            plan = TaskPlan(
                objective=context.objective,
                reasoning=result.get("reasoning", ""),
                steps=[TaskStep(**step) for step in result.get("steps", [])],
            )
        except Exception as exc:
            logger.warning("Planner fell back to heuristic plan: %s", exc)
            plan = self._heuristic_plan(context.objective)

        await self.emit(context.task_id, "planning_finished", {"step_count": len(plan.steps)})
        return AgentResponse(
            success=True,
            summary=f"Created a {len(plan.steps)} step plan.",
            data={"plan": plan.model_dump(mode="json")},
            memory_entries=[
                {
                    "document": f"Plan for '{context.objective}': {plan.reasoning}",
                    "metadata": {"agent": self.name.value, "type": "plan"},
                }
            ],
        )

    def _heuristic_plan(self, objective: str) -> TaskPlan:
        lower = objective.lower()
        steps: list[TaskStep] = []
        if any(token in lower for token in ("search", "research", "scrape", "web", "internet", "browse")):
            steps.append(TaskStep(title="Gather web intelligence", agent=AgentName.web, goal=objective, inputs={"query": objective}, expected_output="Web findings and source-aware summary."))
        if any(token in lower for token in ("image", "visual", "art", "render")):
            steps.append(TaskStep(title="Generate image output", agent=AgentName.vision, goal=objective, inputs={"prompt": objective}, expected_output="Generated image files."))
        if any(token in lower for token in ("voice", "audio", "speech", "transcribe", "speak")):
            steps.append(TaskStep(title="Handle voice task", agent=AgentName.voice, goal=objective, inputs={}, expected_output="Voice transcription or speech output."))
        if any(token in lower for token in ("browser", "open", "file", "folder", "app", "automation")):
            steps.append(TaskStep(title="Perform system action", agent=AgentName.system, goal=objective, inputs={}, expected_output="OS action completed safely."))
        if not steps:
            steps.append(TaskStep(title="Execute local task", agent=AgentName.executor, goal=objective, inputs={}, expected_output="Objective completed locally."))
        return TaskPlan(objective=objective, reasoning="Heuristic fallback plan generated without model output.", steps=steps)
