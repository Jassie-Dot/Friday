from __future__ import annotations

import json
import logging
from typing import Any

from core.llm import OllamaClient

logger = logging.getLogger(__name__)


class WebResearchService:
    """High-level search, scraping, and summarization workflow."""

    def __init__(self, llm: OllamaClient, tools) -> None:
        self.llm = llm
        self.tools = tools

    async def research(self, query: str) -> dict[str, Any]:
        search_result = await self.tools.get("web_search").execute(query=query)
        if not search_result.success:
            return {"success": False, "summary": search_result.output, "results": [], "scraped": []}

        raw_results = search_result.metadata.get("results", [])
        scraped: list[dict[str, Any]] = []
        for item in raw_results[:3]:
            url = item.get("href")
            if not url or not str(url).startswith("http"):
                continue
            try:
                page = await self.tools.get("web_scrape").execute(url=url)
            except Exception as exc:
                logger.warning("Scrape failed for %s: %s", url, exc)
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

        summary = self._fallback_summary(scraped or raw_results, query)
        if scraped:
            try:
                payload = {"query": query, "pages": scraped}
                result = await self.llm.json_response(
                    [
                        {
                            "role": "system",
                            "content": 'Summarize web findings. Return JSON only with {"summary":"...", "sources":[{"title":"...", "url":"..."}]}',
                        },
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                    ],
                    model=self.llm.settings.fast_model,
                )
                if isinstance(result, dict) and result.get("summary"):
                    summary = result["summary"]
            except Exception as exc:
                logger.warning("Web summary fell back to heuristic: %s", exc)

        return {"success": True, "summary": summary, "results": raw_results, "scraped": scraped}

    def _fallback_summary(self, items: list[dict[str, Any]], query: str) -> str:
        if not items:
            return f"No useful web findings were gathered for: {query}"
        lines = []
        for item in items[:3]:
            title = item.get("title", "Untitled")
            url = item.get("url") or item.get("href", "")
            snippet = item.get("snippet") or item.get("body", "") or item.get("content", "")
            lines.append(f"{title} ({url}): {str(snippet)[:180]}")
        return "\n".join(lines)
