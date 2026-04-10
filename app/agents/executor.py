from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName


class ExecutorAgent(BaseAgent):
    name = AgentName.executor
    description = "Runs Python, shell, and filesystem operations for local execution tasks."

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "executor_started", {"step": context.step.title if context.step else "unspecified"})

        step = context.step
        fallback = self._fallback_plan(context)
        plan = await self._tool_plan(
            context,
            instructions=(
                "Use shell for command-line workflows, python for generated code snippets, and filesystem for reads or writes."
            ),
            fallback=fallback,
        )
        response = await self._execute_tool(plan["tool"], plan.get("args", {}))
        await self.emit(
            context.task_id,
            "executor_finished",
            {"tool": plan["tool"], "success": response.success},
        )
        if step:
            response.summary = response.summary or f"Executed step: {step.title}"
        return response

    def _fallback_plan(self, context: AgentContext) -> dict[str, object]:
        step = context.step
        if step and "command" in step.inputs:
            return {"tool": "shell", "args": {"command": step.inputs["command"]}, "reasoning": "Direct command provided."}
        if step and "code" in step.inputs:
            return {"tool": "python", "args": {"code": step.inputs["code"]}, "reasoning": "Direct code provided."}
        if step and "path" in step.inputs:
            args = {"path": step.inputs["path"], "action": step.inputs.get("action", "read")}
            if "content" in step.inputs:
                args["content"] = step.inputs["content"]
            return {"tool": "filesystem", "args": args, "reasoning": "Filesystem path provided."}
        return {
            "tool": "shell",
            "args": {"command": "cmd.exe /c dir"},
            "reasoning": "Fallback workspace inspection.",
        }
