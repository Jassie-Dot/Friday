from __future__ import annotations

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName


class SystemAgent(BaseAgent):
    name = AgentName.system
    description = "Controls files, applications, browser automation, and system inspection."

    def __init__(self, *args, system, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.system = system

    async def run(self, context: AgentContext) -> AgentResponse:
        plan = await self._tool_plan(
            context,
            instructions="Prefer filesystem for file tasks, browser for webpage interaction, system_control for processes or app launch, and shell only when clearly needed.",
            fallback=self._fallback_plan(context),
        )
        return await self._execute_tool(plan["tool"], plan.get("args", {}))

    def _fallback_plan(self, context: AgentContext) -> dict[str, object]:
        step = context.step
        if step and "url" in step.inputs:
            return {"tool": "browser", "args": {"url": step.inputs["url"], "action": "extract"}}
        if step and "target" in step.inputs:
            return {"tool": "system_control", "args": {"action": "open_app", "target": step.inputs["target"]}}
        if step and "path" in step.inputs:
            return {"tool": "filesystem", "args": {"path": step.inputs["path"], "action": step.inputs.get("action", "read")}}
        return {"tool": "system_control", "args": {"action": "list_processes"}}
