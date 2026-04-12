from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from core.events import EventBus
from core.llm import OllamaClient
from core.models import AgentEvent, AgentName, MemoryHit, StepExecution, TaskStep
from core.prompting import PromptLibrary
from core.realtime import RealtimeHub
from memory.store import MemoryStore
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentContext(BaseModel):
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
    name: AgentName
    description: str

    def __init__(
        self,
        llm: OllamaClient,
        fast_llm: OllamaClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        events: EventBus,
        realtime: RealtimeHub,
        prompts: PromptLibrary | None = None,
    ) -> None:
        self.llm = llm
        self.fast_llm = fast_llm
        self.memory = memory
        self.tools = tools
        self.events = events
        self.realtime = realtime
        self.prompts = prompts
        self._events: list[AgentEvent] = []

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResponse:
        raise NotImplementedError

    def tool_catalog(self) -> list[dict[str, str]]:
        return self.tools.describe_for_agent(self.name.value)

    async def emit(self, task_id: str, message_type: str, payload: dict[str, Any]) -> None:
        await self.events.publish(
            AgentEvent(
                source=self.name,
                task_id=task_id,
                message_type=message_type,
                payload=payload,
            )
        )

    def resolve_prompt(self, key: str, default_text: str) -> tuple[str, str]:
        if self.prompts is None:
            return default_text, "default"
        return self.prompts.resolve(key, default_text)

    async def _tool_plan(self, context: AgentContext, instructions: str, fallback: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "objective": context.objective,
            "step": context.step.model_dump() if context.step else None,
            "context": context.task_context,
            "available_tools": self.tool_catalog(),
            "instructions": instructions,
        }
        try:
            result = await self.fast_llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a local autonomous agent. Respond with raw valid JSON only. Do NOT use markdown blocks like ```json."
                            'Choose a single tool. Output schema: {"tool":"...", "args":{}, "reasoning":"..."}'
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                ]
            )
            if isinstance(result, dict) and result.get("tool"):
                return result
        except Exception as exc:
            logger.warning("%s tool selection fell back to heuristic: %s", self.name.value, exc)
        return fallback

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> AgentResponse:
        result = await self.tools.get(tool_name).execute(**args)
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
