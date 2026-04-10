from __future__ import annotations

import asyncio
import os
import platform
import subprocess
from typing import Any

from core.security import PermissionPolicy, SecurityError
from tools.base import BaseTool, ToolResult


class SystemControlTool(BaseTool):
    name = "system_control"
    description = "Launches applications, lists processes, and performs basic OS actions."

    def __init__(self, policy: PermissionPolicy) -> None:
        self.policy = policy

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "list_processes")

        if action == "open_app":
            try:
                self.policy.validate_app_launch()
            except SecurityError as exc:
                return ToolResult(success=False, output=str(exc))
            target = kwargs.get("target")
            if not target:
                return ToolResult(success=False, output="Missing 'target' argument.")
            subprocess.Popen(target, shell=True)
            return ToolResult(success=True, output=f"Launched application: {target}")

        if action == "list_processes":
            command = "tasklist" if os.name == "nt" else "ps -A"
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            combined = output if not err else f"{output}\n{err}".strip()
            return ToolResult(success=process.returncode == 0, output=combined, metadata={"platform": platform.system()})

        return ToolResult(success=False, output=f"Unsupported system action: {action}")
