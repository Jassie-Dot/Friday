from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.debug import DebugAgent
from app.agents.executor import ExecutorAgent
from app.agents.memory import MemoryAgent
from app.agents.planner import PlannerAgent
from app.agents.system import SystemAgent
from app.agents.vision import VisionAgent
from app.agents.voice import VoiceAgent
from app.agents.web import WebAgent
from app.core.events import EventBus
from app.llm.ollama import OllamaClient
from app.memory.store import MemoryStore
from app.schemas.tasks import AgentName
from app.tools.registry import ToolRegistry


class AgentRegistry:
    def __init__(
        self,
        llm: OllamaClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        events: EventBus,
    ) -> None:
        self._agents: dict[AgentName, BaseAgent] = {
            AgentName.planner: PlannerAgent(llm, memory, tools, events),
            AgentName.executor: ExecutorAgent(llm, memory, tools, events),
            AgentName.debug: DebugAgent(llm, memory, tools, events),
            AgentName.memory: MemoryAgent(llm, memory, tools, events),
            AgentName.web: WebAgent(llm, memory, tools, events),
            AgentName.vision: VisionAgent(llm, memory, tools, events),
            AgentName.system: SystemAgent(llm, memory, tools, events),
            AgentName.voice: VoiceAgent(llm, memory, tools, events),
        }

    def get(self, name: AgentName) -> BaseAgent:
        return self._agents[name]

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": agent_name.value,
                "description": agent.description,
            }
            for agent_name, agent in self._agents.items()
        ]
