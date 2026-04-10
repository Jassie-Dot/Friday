from __future__ import annotations

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName


class ExecutorAgent(BaseAgent):
    name = AgentName.executor
    description = "Runs shell, Python, and filesystem operations."

    async def run(self, context: AgentContext) -> AgentResponse:
        step = context.step
        await self.emit(context.task_id, "executor_started", {"step": step.title if step else "unspecified"})
        plan = await self._tool_plan(
            context,
            instructions="Use shell for command workflows, python for snippets, and filesystem for direct file operations.",
            fallback=self._fallback_plan(context),
        )
        response = await self._execute_tool(plan["tool"], plan.get("args", {}))
        await self.emit(context.task_id, "executor_finished", {"tool": plan["tool"], "success": response.success})
        return response

    def _fallback_plan(self, context: AgentContext) -> dict[str, object]:
        step = context.step
        if step and "command" in step.inputs:
            return {"tool": "shell", "args": {"command": step.inputs["command"]}}
        if step and "code" in step.inputs:
            return {"tool": "python", "args": {"code": step.inputs["code"]}}
        if step and "path" in step.inputs:
            args = {"path": step.inputs["path"], "action": step.inputs.get("action", "read")}
            if "content" in step.inputs:
                args["content"] = step.inputs["content"]
            return {"tool": "filesystem", "args": args}
        return {"tool": "shell", "args": {"command": "cmd.exe /c dir"}}
