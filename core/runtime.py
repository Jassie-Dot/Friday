from __future__ import annotations

from agents.registry import AgentRegistry
from core.config import Settings
from core.events import EventBus
from core.llm import OllamaClient
from core.logging import configure_logging
from core.orchestrator import FridayOrchestrator
from core.realtime import RealtimeHub
from core.security import PermissionPolicy
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
        self.tools = ToolRegistry(settings, self.policy)
        self.web = WebResearchService(self.llm, self.tools)
        self.system = SystemController(self.tools)
        self.agents = AgentRegistry(
            llm=self.llm,
            fast_llm=self.fast_llm,
            memory=self.memory,
            tools=self.tools,
            events=self.events,
            realtime=self.realtime,
            web=self.web,
            system=self.system,
        )
        self.orchestrator = FridayOrchestrator(
            llm=self.llm,
            memory=self.memory,
            agents=self.agents,
            realtime=self.realtime,
            logs_root=settings.logs_root,
        )

    async def start(self) -> None:
        await self.orchestrator.start()

    async def stop(self) -> None:
        await self.orchestrator.stop()
        await self.llm.close()

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
            "ollama": llm_info,
        }
