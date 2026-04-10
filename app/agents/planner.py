from __future__ import annotations

import json
import logging

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName, TaskPlan, TaskStep

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    name = AgentName.planner
    description = "Breaks objectives into structured steps for specialized agents."

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
                {"name": "voice", "best_for": "speech-to-text and text-to-speech"},
                {"name": "system", "best_for": "browser control, OS actions, file management"},
            ],
        }

        try:
            plan_data = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are the planner for a local autonomous system. "
                            "Return JSON only with the schema "
                            '{"reasoning":"...", "steps":[{"title":"...", "agent":"executor|web|vision|voice|system", '
                            '"goal":"...", "inputs":{}, "expected_output":"..."}]}. '
                            "Keep steps concrete, safe, and under 8 items."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ],
                model=self.llm.settings.fast_model,
            )
            plan = TaskPlan(
                objective=context.objective,
                reasoning=plan_data.get("reasoning", ""),
                steps=[TaskStep(**step) for step in plan_data.get("steps", [])],
            )
        except Exception as exc:
            logger.warning("Planner failed; using heuristic plan: %s", exc)
            plan = self._heuristic_plan(context.objective)

        await self.emit(
            context.task_id,
            "planning_finished",
            {"step_count": len(plan.steps), "reasoning": plan.reasoning},
        )
        return AgentResponse(
            success=True,
            summary=f"Created a {len(plan.steps)} step plan.",
            data={"plan": plan.model_dump(mode="json")},
            memory_entries=[
                {
                    "document": f"Plan for objective '{context.objective}': {plan.reasoning}",
                    "metadata": {"agent": self.name.value, "type": "plan"},
                }
            ],
        )

    def _heuristic_plan(self, objective: str) -> TaskPlan:
        # This fallback keeps FRIDAY operational when the primary planning model
        # is offline. It intentionally routes by capability keywords.
        lower = objective.lower()
        steps: list[TaskStep] = []

        if any(token in lower for token in ("search", "web", "scrape", "internet", "online", "research")):
            steps.append(
                TaskStep(
                    title="Gather web intelligence",
                    agent=AgentName.web,
                    goal=objective,
                    inputs={"query": objective},
                    expected_output="Relevant internet findings and summaries.",
                )
            )

        if any(token in lower for token in ("image", "picture", "art", "illustration", "render")):
            steps.append(
                TaskStep(
                    title="Generate imagery",
                    agent=AgentName.vision,
                    goal=objective,
                    inputs={"prompt": objective},
                    expected_output="Generated local image assets.",
                )
            )

        if any(token in lower for token in ("voice", "speech", "audio", "transcribe", "tts")):
            steps.append(
                TaskStep(
                    title="Handle audio request",
                    agent=AgentName.voice,
                    goal=objective,
                    inputs={},
                    expected_output="Audio transcription or speech output.",
                )
            )

        if any(token in lower for token in ("browser", "open", "app", "filesystem", "directory", "file")):
            steps.append(
                TaskStep(
                    title="Perform system action",
                    agent=AgentName.system,
                    goal=objective,
                    inputs={},
                    expected_output="System-level action completed safely.",
                )
            )

        if not steps:
            steps.append(
                TaskStep(
                    title="Execute local task",
                    agent=AgentName.executor,
                    goal=objective,
                    inputs={},
                    expected_output="Objective completed locally.",
                )
            )

        return TaskPlan(objective=objective, reasoning="Heuristic plan generated without model output.", steps=steps)
