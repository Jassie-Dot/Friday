from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.events import EventBus
from app.llm.ollama import OllamaClient
from app.memory.store import MemoryStore
from app.schemas.tasks import AgentMessage, AgentName, MemoryHit, StepExecution, TaskStep
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentContext(BaseModel):
    """Structured execution envelope shared between the orchestrator and agents."""

    task_id: str
    objective: str
    task_context: dict[str, Any] = Field(default_factory=dict)
    step: TaskStep | None = None
    memories: list[MemoryHit] = Field(default_factory=list)
    previous_results: list[StepExecution] = Field(default_factory=list)
    failure_reason: str | None = None


class AgentResponse(BaseModel):
    success: bool
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    memory_entries: list[dict[str, Any]] = Field(default_factory=list)


class BaseAgent(ABC):
    """Base contract for all FRIDAY agents.

    Agents reason locally, emit structured events, and optionally call tools
    through the registry. Tool planning is centralized here so specialized
    agents can stay small and focused.
    """

    name: AgentName
    description: str

    def __init__(
        self,
        llm: OllamaClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        events: EventBus,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.events = events

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResponse:
        raise NotImplementedError

    async def emit(self, task_id: str, message_type: str, payload: dict[str, Any]) -> None:
        await self.events.publish(
            AgentMessage(
                source=self.name,
                task_id=task_id,
                message_type=message_type,
                payload=payload,
            )
        )

    def tool_catalog(self) -> list[dict[str, str]]:
        return self.tools.describe_for_agent(self.name.value)

    async def _tool_plan(
        self,
        context: AgentContext,
        instructions: str,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        # Tool selection is itself a local-model task. The fallback keeps the
        # system usable even when Ollama is unavailable or returns malformed JSON.
        prompt = {
            "objective": context.objective,
            "step": context.step.model_dump() if context.step else None,
            "context": context.task_context,
            "available_tools": self.tool_catalog(),
            "instructions": instructions,
        }
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a local autonomous agent. Respond with valid JSON only. "
                            "Choose a single tool and a minimal arguments object. "
                            'Output schema: {"tool": "...", "args": {...}, "reasoning": "..."}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=True),
                    },
                ]
            )
            if isinstance(result, dict) and result.get("tool"):
                return result
        except Exception as exc:
            logger.warning("%s tool planning fell back to heuristic: %s", self.name.value, exc)
        return fallback

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> AgentResponse:
        tool = self.tools.get(tool_name)
        result = await tool.execute(**args)
        return AgentResponse(
            success=result.success,
            summary=result.output[:500] if result.output else "",
            data={"tool": tool_name, "args": args, "result": result.model_dump()},
            error=None if result.success else result.output,
            memory_entries=[
                {
                    "document": f"{self.name.value} used {tool_name}: {result.output[:1000]}",
                    "metadata": {"agent": self.name.value, "tool": tool_name},
                }
            ]
            if result.success
            else [],
        )
