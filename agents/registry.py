from __future__ import annotations

from agents.base import BaseAgent
from agents.chat import ChatAgent
from agents.critic import CriticAgent
from agents.debugger import DebugAgent
from agents.evolution import EvolutionAgent
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
from core.prompting import PromptLibrary
from core.realtime import RealtimeHub
from memory.store import MemoryStore
from tools.registry import ToolRegistry


class AgentRegistry:
    def __init__(
        self,
        *,
        llm: OllamaClient,
        fast_llm: OllamaClient,
        memory: MemoryStore,
        tools: ToolRegistry,
        events: EventBus,
        realtime: RealtimeHub,
        prompts: PromptLibrary,
        web,
        system,
    ) -> None:
        self._agents: dict[AgentName, BaseAgent] = {
            AgentName.planner: PlannerAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.executor: ExecutorAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.critic: CriticAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.evolution: EvolutionAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.debug: DebugAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.memory: MemoryAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.web: WebAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts, web=web),
            AgentName.system: SystemAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts, system=system),
            AgentName.vision: VisionAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.voice: VoiceAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
            AgentName.chat: ChatAgent(llm, fast_llm, memory, tools, events, realtime, prompts=prompts),
        }

    def get(self, name: AgentName) -> BaseAgent:
        return self._agents[name]

    def describe(self) -> list[dict[str, str]]:
        return [{"name": name.value, "description": agent.description} for name, agent in self._agents.items()]
