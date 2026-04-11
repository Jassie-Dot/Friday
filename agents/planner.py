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
                {"name": "chat", "best_for": "greetings, questions, explanations, conversation, general knowledge"},
                {"name": "executor", "best_for": "code execution, shell commands, file operations, python scripts"},
                {"name": "web", "best_for": "internet search, scraping, summarization of web pages"},
                {"name": "vision", "best_for": "image generation and editing"},
                {"name": "voice", "best_for": "speech to text transcription and text to speech synthesis"},
                {"name": "system", "best_for": "browser control, OS actions, app launching, automation"},
            ],
        }
        try:
            result = await self.fast_llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are FRIDAY's mission planner — the tactical brain of an Iron Man AI companion. "
                            "Break the Boss's objective into precise executable steps. Return JSON only with "
                            '{"reasoning":"...", "steps":[{"title":"...", "agent":"chat", '
                            '"goal":"...", "inputs":{}, "expected_output":"..."}]}. '
                            "The 'agent' MUST be exactly one of: chat, executor, web, vision, voice, system. "
                            "Use 'chat' for greetings, questions, general conversation, and explanations. "
                            "Keep the plan concrete, safe, and under 8 steps. "
                            "For simple conversational requests, use exactly ONE chat step."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ]
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
        if any(token in lower for token in ("image", "visual", "art", "render", "draw", "picture")):
            steps.append(TaskStep(title="Generate image output", agent=AgentName.vision, goal=objective, inputs={"prompt": objective}, expected_output="Generated image files."))
        if any(token in lower for token in ("transcribe", "dictation", "record audio")):
            steps.append(TaskStep(title="Handle voice task", agent=AgentName.voice, goal=objective, inputs={}, expected_output="Voice transcription or speech output."))
        if any(token in lower for token in ("browser", "open app", "launch", "automation")):
            steps.append(TaskStep(title="Perform system action", agent=AgentName.system, goal=objective, inputs={}, expected_output="OS action completed safely."))
        if any(token in lower for token in ("run", "execute", "script", "code", "compile", "build", "install")):
            steps.append(TaskStep(title="Execute local task", agent=AgentName.executor, goal=objective, inputs={}, expected_output="Objective completed locally."))
        if not steps:
            # Default: treat as conversational
            steps.append(TaskStep(title="Respond to user", agent=AgentName.chat, goal=objective, inputs={}, expected_output="A helpful conversational response."))
        return TaskPlan(objective=objective, reasoning="Heuristic fallback plan generated without model output.", steps=steps)
