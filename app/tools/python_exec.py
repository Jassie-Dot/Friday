from __future__ import annotations

import asyncio
import sys
from typing import Any

from app.core.config import Settings
from app.core.security import PermissionPolicy, SecurityError
from app.tools.base import BaseTool, ToolResult


class PythonExecutionTool(BaseTool):
    name = "python"
    description = "Executes local Python snippets in a subprocess."

    def __init__(self, settings: Settings, policy: PermissionPolicy) -> None:
        self.settings = settings
        self.policy = policy

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not self.settings.allow_python:
            return ToolResult(success=False, output="Python execution is disabled.")

        code = kwargs.get("code")
        if not code:
            return ToolResult(success=False, output="Missing 'code' argument.")

        try:
            cwd = self.policy.ensure_path_allowed(kwargs.get("cwd", self.settings.workspace_root))
        except SecurityError as exc:
            return ToolResult(success=False, output=str(exc))

        timeout = min(
            int(kwargs.get("timeout", self.settings.max_shell_timeout_seconds)),
            self.settings.max_shell_timeout_seconds,
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return ToolResult(success=False, output=f"Python execution timed out after {timeout}s.")

        output = stdout.decode("utf-8", errors="replace").strip()
        error_output = stderr.decode("utf-8", errors="replace").strip()
        combined = output if not error_output else f"{output}\n{error_output}".strip()
        return ToolResult(
            success=process.returncode == 0,
            output=combined,
            metadata={"returncode": process.returncode, "cwd": str(cwd)},
        )
