from __future__ import annotations

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName


class WebAgent(BaseAgent):
    name = AgentName.web
    description = "Performs web search, scraping, and summarization."

    def __init__(self, *args, web, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.web = web

    async def run(self, context: AgentContext) -> AgentResponse:
        query = (context.step.inputs.get("query") if context.step else None) or context.objective
        await self.emit(context.task_id, "web_started", {"query": query})
        result = await self.web.research(query)
        await self.emit(context.task_id, "web_finished", {"success": result["success"], "query": query})
        return AgentResponse(
            success=result["success"],
            summary=result["summary"],
            data=result,
            error=None if result["success"] else result["summary"],
            memory_entries=[
                {
                    "document": f"Web research for '{query}': {result['summary']}",
                    "metadata": {"agent": self.name.value, "type": "web_research"},
                }
            ]
            if result["success"]
            else [],
        )
