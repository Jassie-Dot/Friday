from __future__ import annotations

from agents.base import BaseAgent
from agents.debugger import DebugAgent
from agents.executor import ExecutorAgent
from agents.memory_agent import MemoryAgent
from agents.planner import PlannerAgent
from agents.system import SystemAgent
from agents.vision import VisionAgent
from agents.voice import VoiceAgent
from agents.web import WebAgent
from core.events import EventBus
from core.llm import OllamaClient
from core.models import AgentName
from core.realtime import RealtimeHub
from memory.store import MemoryStore
from tools.registry import ToolRegistry


class AgentRegistry:
    def __init__(
        self,
        *,
        llm: OllamaClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        events: EventBus,
        realtime: RealtimeHub,
        web,
        system,
    ) -> None:
        self._agents: dict[AgentName, BaseAgent] = {
            AgentName.planner: PlannerAgent(llm, memory, tools, events, realtime),
            AgentName.executor: ExecutorAgent(llm, memory, tools, events, realtime),
            AgentName.debug: DebugAgent(llm, memory, tools, events, realtime),
            AgentName.memory: MemoryAgent(llm, memory, tools, events, realtime),
            AgentName.web: WebAgent(llm, memory, tools, events, realtime, web=web),
            AgentName.system: SystemAgent(llm, memory, tools, events, realtime, system=system),
            AgentName.vision: VisionAgent(llm, memory, tools, events, realtime),
            AgentName.voice: VoiceAgent(llm, memory, tools, events, realtime),
        }

    def get(self, name: AgentName) -> BaseAgent:
        return self._agents[name]

    def describe(self) -> list[dict[str, str]]:
        return [{"name": name.value, "description": agent.description} for name, agent in self._agents.items()]
