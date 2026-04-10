from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName


class MemoryAgent(BaseAgent):
    name = AgentName.memory
    description = "Stores and retrieves long-term semantic memory."

    async def run(self, context: AgentContext) -> AgentResponse:
        step = context.step
        action = step.inputs.get("action", "query") if step else "query"

        if action == "store":
            document = step.inputs.get("document", context.objective) if step else context.objective
            metadata = step.inputs.get("metadata", {}) if step else {}
            memory_id = self.memory.add(document, metadata)
            return AgentResponse(success=True, summary=f"Stored memory {memory_id}.", data={"memory_id": memory_id})

        query = step.inputs.get("query", context.objective) if step else context.objective
        results = self.memory.query(query, limit=5)
        return AgentResponse(
            success=True,
            summary=f"Retrieved {len(results)} memories.",
            data={"results": [result.model_dump() for result in results]},
        )
