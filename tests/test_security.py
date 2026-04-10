from pathlib import Path

from core.config import Settings
from core.security import PermissionPolicy, SecurityError


def test_shell_policy_blocks_destructive_commands():
    workspace = Path.cwd() / "workspace"
    settings = Settings(workspace_root=workspace, data_root=workspace / ".friday", allow_destructive_shell=False)
    policy = PermissionPolicy(settings)

    try:
        policy.validate_shell_command("rm -rf /")
    except SecurityError:
        return

    raise AssertionError("Expected destructive shell command to be blocked.")


def test_allowed_path_stays_inside_workspace():
    workspace = Path.cwd() / "workspace"
    settings = Settings(workspace_root=workspace, data_root=workspace / ".friday")
    policy = PermissionPolicy(settings)
    resolved = policy.ensure_path_allowed("app/main.py")
    assert resolved == (workspace / "app/main.py").resolve()
