from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName


class VisionAgent(BaseAgent):
    name = AgentName.vision
    description = "Creates and edits images with local diffusion models."

    async def run(self, context: AgentContext) -> AgentResponse:
        step = context.step
        prompt = (step.inputs.get("prompt") if step else None) or context.objective
        args = {
            "prompt": prompt,
            "negative_prompt": step.inputs.get("negative_prompt") if step else None,
            "output_path": step.inputs.get("output_path") if step else None,
            "init_image_path": step.inputs.get("init_image_path") if step else None,
            "batch_size": step.inputs.get("batch_size", 1) if step else 1,
            "steps": step.inputs.get("steps", 30) if step else 30,
        }
        return await self._execute_tool("image", args)
