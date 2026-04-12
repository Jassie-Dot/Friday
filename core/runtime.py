from __future__ import annotations

from agents.chat import ChatAgent
from agents.critic import CriticAgent
from agents.evolution import EvolutionAgent
from agents.planner import PlannerAgent
from agents.registry import AgentRegistry
from core.config import Settings
from core.evolution import RuntimeEvolutionService
from core.events import EventBus
from core.intelligence import HybridIntelligenceService
from core.llm import OllamaClient
from core.logging import configure_logging
from core.orchestrator import FridayOrchestrator
from core.prompting import PromptLibrary
from core.realtime import RealtimeHub
from core.security import PermissionPolicy
from core.voice_engine import LocalVoiceEngine
from core.voice_session import VoiceSessionManager
from memory.embeddings import build_embedding_provider
from memory.store import MemoryStore
from system_control.controller import SystemController
from tools.registry import ToolRegistry
from web_agent.service import WebResearchService


class FridayRuntime:
    """Bootstraps and owns the backend runtime graph."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        configure_logging(settings.log_level, settings.logs_root / "friday.log")

        self.events = EventBus()
        self.realtime = RealtimeHub(settings.frontend_mode)
        self.events.subscribe(self.realtime.record_event)

        self.llm = OllamaClient(settings, model=settings.primary_model)
        self.fast_llm = OllamaClient(settings, model=settings.fast_model)
        self.policy = PermissionPolicy(settings)
        self.memory = MemoryStore(settings, build_embedding_provider(settings))
        self.prompts = PromptLibrary(settings.data_root)
        self.tools = ToolRegistry(settings, self.policy)
        self.web = WebResearchService(self.llm, self.tools)
        self.system = SystemController(self.tools)
        self.voice = LocalVoiceEngine(settings)
        self.intelligence = HybridIntelligenceService(
            settings=settings,
            llm=self.llm,
            fast_llm=self.fast_llm,
            memory=self.memory,
            prompts=self.prompts,
            realtime=self.realtime,
        )
        self.agents = AgentRegistry(
            llm=self.llm,
            fast_llm=self.fast_llm,
            memory=self.memory,
            tools=self.tools,
            events=self.events,
            realtime=self.realtime,
            prompts=self.prompts,
            web=self.web,
            system=self.system,
        )
        self.evolution = RuntimeEvolutionService(
            prompts=self.prompts,
            memory=self.memory,
            prompt_defaults={
                "chat.system": ChatAgent.SYSTEM_PROMPT,
                "planner.system": PlannerAgent.SYSTEM_PROMPT,
                "critic.system": CriticAgent.SYSTEM_PROMPT,
                "evolution.system": EvolutionAgent.SYSTEM_PROMPT,
                "intelligence.system": HybridIntelligenceService.SYSTEM_PROMPT,
            },
        )
        self.orchestrator = FridayOrchestrator(
            llm=self.llm,
            memory=self.memory,
            agents=self.agents,
            realtime=self.realtime,
            logs_root=settings.logs_root,
            evolution=self.evolution,
        )
        self.sessions = VoiceSessionManager(
            settings=settings,
            realtime=self.realtime,
            voice=self.voice,
            intelligence=self.intelligence,
            orchestrator=self.orchestrator,
        )

    async def start(self) -> None:
        await self.orchestrator.start()

    async def stop(self) -> None:
        await self.orchestrator.stop()
        await self.llm.close()
        await self.fast_llm.close()

    async def health(self) -> dict[str, object]:
        llm_ok = True
        llm_info: dict[str, object] = {}
        try:
            llm_info = await self.llm.health()
        except Exception as exc:
            llm_ok = False
            llm_info = {"error": str(exc)}

        return {
            "app": self.settings.app_name,
            "status": "ok" if llm_ok else "degraded",
            "frontend_mode": self.settings.frontend_mode.value,
            "workspace_root": str(self.settings.workspace_root),
            "data_root": str(self.settings.data_root),
            "logs_root": str(self.settings.logs_root),
            "models": {
                "primary": self.settings.primary_model,
                "fast": self.settings.fast_model,
            },
            "voice": {
                "whisper_model": self.settings.whisper_model_size,
                "piper_model_path": self.settings.piper_model_path,
            },
            "evolution_enabled": self.settings.evolution_enabled,
            "ollama": llm_info,
        }
