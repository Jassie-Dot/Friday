from __future__ import annotations

import asyncio
from typing import Any

from core.config import Settings
from core.security import PermissionPolicy, SecurityError
from tools.base import BaseTool, ToolResult


class ShellTool(BaseTool):
    name = "shell"
    description = "Runs approved shell commands within the workspace."

    def __init__(self, settings: Settings, policy: PermissionPolicy) -> None:
        self.settings = settings
        self.policy = policy

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command")
        if not command:
            return ToolResult(success=False, output="Missing 'command' argument.")
        try:
            self.policy.validate_shell_command(command)
            cwd = self.policy.ensure_path_allowed(kwargs.get("cwd", self.settings.workspace_root))
        except SecurityError as exc:
            return ToolResult(success=False, output=str(exc))

        timeout = min(int(kwargs.get("timeout", self.settings.max_shell_timeout_seconds)), self.settings.max_shell_timeout_seconds)
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return ToolResult(success=False, output=f"Command timed out after {timeout}s.")

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        combined = out if not err else f"{out}\n{err}".strip()
        return ToolResult(success=process.returncode == 0, output=combined, metadata={"returncode": process.returncode, "cwd": str(cwd)})
