from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.base import AgentContext, AgentResponse, BaseAgent
from app.schemas.tasks import AgentName

logger = logging.getLogger(__name__)


class WebAgent(BaseAgent):
    name = AgentName.web
    description = "Searches, scrapes, validates, and summarizes internet resources."

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "web_started", {"objective": context.objective})
        step = context.step
        query = (step.inputs.get("query") if step else None) or context.objective

        search_result = await self.tools.get("web_search").execute(query=query)
        if not search_result.success:
            return AgentResponse(success=False, summary="Web search failed.", error=search_result.output)

        raw_results = search_result.metadata.get("results", [])
        scraped: list[dict[str, Any]] = []
        # Search is intentionally separated from scraping so the agent can inspect
        # sources first, then fetch only a small validated subset.
        for item in raw_results[:3]:
            url = item.get("href")
            if not url or not str(url).startswith("http"):
                continue
            try:
                page = await self.tools.get("web_scrape").execute(url=url)
            except Exception as exc:
                logger.warning("Failed scraping %s: %s", url, exc)
                continue
            if page.success:
                scraped.append(
                    {
                        "title": item.get("title", page.metadata.get("title", url)),
                        "url": url,
                        "snippet": item.get("body", ""),
                        "content": page.output[:4000],
                    }
                )

        summary_text = self._fallback_summary(scraped or raw_results, query)
        if scraped:
            try:
                result = await self.llm.json_response(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Summarize web findings for a local autonomous system. Return JSON only with "
                                '{"summary":"...", "sources":[{"title":"...", "url":"..."}]}. '
                                "Be concise and factual."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps({"query": query, "pages": scraped}, ensure_ascii=True),
                        },
                    ],
                    model=self.llm.settings.fast_model,
                )
                if isinstance(result, dict):
                    summary_text = result.get("summary", summary_text)
            except Exception as exc:
                logger.warning("Web summary fell back to heuristic: %s", exc)

        await self.emit(context.task_id, "web_finished", {"results": len(raw_results), "scraped": len(scraped)})
        return AgentResponse(
            success=True,
            summary=summary_text,
            data={"query": query, "results": raw_results, "scraped": scraped},
            memory_entries=[
                {
                    "document": f"Web research for '{query}': {summary_text}",
                    "metadata": {"agent": self.name.value, "type": "web_research"},
                }
            ],
        )

    def _fallback_summary(self, items: list[dict[str, Any]], query: str) -> str:
        if not items:
            return f"No relevant web results were gathered for: {query}"
        lines = []
        for item in items[:3]:
            title = item.get("title", "Untitled")
            url = item.get("url") or item.get("href", "")
            snippet = item.get("snippet") or item.get("body", "") or item.get("content", "")
            lines.append(f"{title} ({url}): {str(snippet)[:180]}")
        return "\n".join(lines)
