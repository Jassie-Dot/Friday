from __future__ import annotations

from core.config import Settings
from core.security import PermissionPolicy
from tools.browser import BrowserAutomationTool
from tools.filesystem import FileSystemTool
from tools.image import ImageGenerationTool
from tools.python_exec import PythonExecutionTool
from tools.shell import ShellTool
from tools.system import SystemControlTool
from tools.voice import VoiceTool
from tools.web import WebScrapeTool, WebSearchTool


class ToolRegistry:
    def __init__(self, settings: Settings, policy: PermissionPolicy) -> None:
        self._tools = {
            "filesystem": FileSystemTool(policy),
            "shell": ShellTool(settings, policy),
            "python": PythonExecutionTool(settings, policy),
            "web_search": WebSearchTool(settings),
            "web_scrape": WebScrapeTool(),
            "browser": BrowserAutomationTool(settings),
            "image": ImageGenerationTool(settings),
            "voice": VoiceTool(settings),
            "system_control": SystemControlTool(policy),
        }
        self._agent_tools = {
            "planner": [],
            "executor": ["filesystem", "shell", "python"],
            "debug": ["filesystem", "shell", "python"],
            "memory": [],
            "web": ["web_search", "web_scrape", "browser"],
            "system": ["filesystem", "shell", "browser", "system_control"],
            "vision": ["image"],
            "voice": ["voice"],
        }

    def get(self, name: str):
        return self._tools[name]

    def describe_for_agent(self, agent_name: str) -> list[dict[str, str]]:
        return [
            {"name": name, "description": self._tools[name].description}
            for name in self._agent_tools.get(agent_name, [])
        ]
