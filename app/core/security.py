from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class SecurityError(RuntimeError):
    """Raised when a tool request violates policy."""


class PermissionPolicy:
    """Central policy gate for filesystem boundaries and risky shell actions."""

    BLOCKED_SHELL_TOKENS = (
        "rm -rf",
        "del /f /s /q",
        "format ",
        "shutdown ",
        "reboot",
        "mkfs",
        "diskpart",
        "reg delete",
        "cipher /w",
        "takeown /f c:\\",
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.allowed_roots = {
            settings.workspace_root.resolve(),
            settings.data_root.resolve(),
        }

    def resolve_path(self, raw_path: str | Path) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (self.settings.workspace_root / path).resolve()
        else:
            path = path.resolve()
        return path

    def ensure_path_allowed(self, raw_path: str | Path) -> Path:
        # Every file tool resolves paths through the workspace/data roots so agents
        # cannot wander into arbitrary locations on the host.
        path = self.resolve_path(raw_path)
        if not any(root == path or root in path.parents for root in self.allowed_roots):
            raise SecurityError(f"Path '{path}' is outside approved roots.")
        return path

    def validate_shell_command(self, command: str) -> None:
        # The shell tool is intentionally conservative. Destructive commands can be
        # enabled for trusted environments, but the default posture is deny-by-default.
        normalized = command.lower()
        if not self.settings.allow_shell:
            raise SecurityError("Shell execution is disabled.")
        if self.settings.allow_destructive_shell:
            return
        for token in self.BLOCKED_SHELL_TOKENS:
            if token in normalized:
                raise SecurityError(f"Command blocked by policy: '{token}'")

    def validate_app_launch(self) -> None:
        if not self.settings.allow_app_launch:
            raise SecurityError("Application launch is disabled. Enable FRIDAY_ALLOW_APP_LAUNCH to use it.")
