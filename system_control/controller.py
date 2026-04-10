from __future__ import annotations

from typing import Any


class SystemController:
    """Thin domain wrapper around low-level system tools."""

    def __init__(self, tools) -> None:
        self.tools = tools

    async def inspect_processes(self) -> dict[str, Any]:
        result = await self.tools.get("system_control").execute(action="list_processes")
        return result.model_dump()

    async def launch_application(self, target: str) -> dict[str, Any]:
        result = await self.tools.get("system_control").execute(action="open_app", target=target)
        return result.model_dump()
