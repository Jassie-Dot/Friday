from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.security import PermissionPolicy
from app.tools.base import BaseTool, ToolResult


class FileSystemTool(BaseTool):
    name = "filesystem"
    description = "Reads, writes, lists, and creates files and directories within approved roots."

    def __init__(self, policy: PermissionPolicy) -> None:
        self.policy = policy

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "read")
        raw_path = kwargs.get("path")
        if raw_path is None:
            return ToolResult(success=False, output="Missing 'path' argument.")

        path = self.policy.ensure_path_allowed(raw_path)

        if action == "read":
            if not path.exists():
                return ToolResult(success=False, output=f"Path not found: {path}")
            if path.is_dir():
                return ToolResult(
                    success=True,
                    output="\n".join(sorted(item.name for item in path.iterdir())),
                    metadata={"path": str(path), "type": "directory"},
                )
            return ToolResult(
                success=True,
                output=path.read_text(encoding="utf-8"),
                metadata={"path": str(path), "type": "file"},
            )

        if action == "write":
            content = kwargs.get("content", "")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Wrote file: {path}", metadata={"path": str(path)})

        if action == "append":
            content = kwargs.get("content", "")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
            return ToolResult(success=True, output=f"Appended file: {path}", metadata={"path": str(path)})

        if action == "mkdir":
            path.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, output=f"Created directory: {path}", metadata={"path": str(path)})

        if action == "list":
            pattern = kwargs.get("pattern", "*")
            recursive = kwargs.get("recursive", False)
            iterator = path.rglob(pattern) if recursive else path.glob(pattern)
            entries = sorted(str(item) for item in iterator)
            return ToolResult(success=True, output="\n".join(entries), metadata={"count": len(entries)})

        return ToolResult(success=False, output=f"Unsupported filesystem action: {action}")
