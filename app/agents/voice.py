from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName


class VoiceAgent(BaseAgent):
    name = AgentName.voice
    description = "Handles local speech recognition and text-to-speech."

    async def run(self, context: AgentContext) -> AgentResponse:
        step = context.step
        action = step.inputs.get("action", "transcribe") if step else "transcribe"
        args = {"action": action}
        if step:
            args.update(step.inputs)
        return await self._execute_tool("voice", args)
