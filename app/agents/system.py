from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName


class SystemAgent(BaseAgent):
    name = AgentName.system
    description = "Controls files, browser automation, system inspection, and app launching."

    async def run(self, context: AgentContext) -> AgentResponse:
        fallback = self._fallback_plan(context)
        plan = await self._tool_plan(
            context,
            instructions=(
                "Prefer filesystem for file tasks, browser for webpage interaction, system_control for processes or app launch, "
                "and shell only when a direct command is clearly needed."
            ),
            fallback=fallback,
        )
        return await self._execute_tool(plan["tool"], plan.get("args", {}))

    def _fallback_plan(self, context: AgentContext) -> dict[str, object]:
        step = context.step
        if step and "url" in step.inputs:
            return {"tool": "browser", "args": {"url": step.inputs["url"], "action": "extract"}, "reasoning": "URL provided."}
        if step and "target" in step.inputs:
            return {
                "tool": "system_control",
                "args": {"action": "open_app", "target": step.inputs["target"]},
                "reasoning": "Explicit application target provided.",
            }
        if step and "path" in step.inputs:
            return {
                "tool": "filesystem",
                "args": {"path": step.inputs["path"], "action": step.inputs.get("action", "read")},
                "reasoning": "File path provided.",
            }
        return {"tool": "system_control", "args": {"action": "list_processes"}, "reasoning": "Fallback system inspection."}
