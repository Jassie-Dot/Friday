from __future__ import annotations

from app.core.config import Settings
from app.core.security import PermissionPolicy
from app.tools.browser import BrowserAutomationTool
from app.tools.filesystem import FileSystemTool
from app.tools.image import ImageGenerationTool
from app.tools.python_exec import PythonExecutionTool
from app.tools.shell import ShellTool
from app.tools.system_control import SystemControlTool
from app.tools.voice import VoiceTool
from app.tools.web import WebScrapeTool, WebSearchTool


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

        self._agent_tool_map = {
            "planner": [],
            "executor": ["filesystem", "shell", "python"],
            "debug": ["filesystem", "shell", "python"],
            "memory": [],
            "web": ["web_search", "web_scrape", "browser"],
            "vision": ["image"],
            "system": ["filesystem", "shell", "browser", "system_control"],
            "voice": ["voice"],
        }

    def get(self, name: str):
        return self._tools[name]

    def names_for_agent(self, agent_name: str) -> list[str]:
        return self._agent_tool_map.get(agent_name, [])

    def describe_for_agent(self, agent_name: str) -> list[dict[str, str]]:
        return [
            {
                "name": tool_name,
                "description": self._tools[tool_name].description,
            }
            for tool_name in self.names_for_agent(agent_name)
        ]
