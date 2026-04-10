from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from core.config import Settings
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Searches the public web using DuckDuckGo."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query")
        if not query:
            return ToolResult(success=False, output="Missing 'query' argument.")

        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=int(kwargs.get("max_results", self.settings.ddg_max_results))):
                results.append(item)
        output = "\n".join(f"{item.get('title', 'Untitled')} | {item.get('href', '')}" for item in results)
        return ToolResult(success=True, output=output, metadata={"results": results})


class WebScrapeTool(BaseTool):
    name = "web_scrape"
    description = "Fetches and extracts readable text from a web page."

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url")
        if not url:
            return ToolResult(success=False, output="Missing 'url' argument.")

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "FRIDAY Local Agent/1.0"})
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()

        title = soup.title.text.strip() if soup.title and soup.title.text else url
        text = " ".join(soup.stripped_strings)[:12000]
        return ToolResult(success=True, output=text, metadata={"title": title, "url": url})
