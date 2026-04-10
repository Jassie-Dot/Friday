from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.tools.base import BaseTool, ToolResult


class BrowserAutomationTool(BaseTool):
    name = "browser"
    description = "Automates a headless browser for extraction and screenshots."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ToolResult(success=False, output="Playwright is not installed.")

        url = kwargs.get("url")
        action = kwargs.get("action", "extract")
        if not url:
            return ToolResult(success=False, output="Missing 'url' argument.")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.browser_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=self.settings.browser_timeout_ms)

            if action == "extract":
                content = await page.text_content("body")
                await browser.close()
                return ToolResult(success=True, output=content or "", metadata={"url": url})

            if action == "screenshot":
                output_path = Path(kwargs.get("output_path", self.settings.generated_dir / "browser-shot.png"))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(output_path), full_page=True)
                await browser.close()
                return ToolResult(success=True, output=f"Saved screenshot to {output_path}", metadata={"path": str(output_path)})

            await browser.close()
            return ToolResult(success=False, output=f"Unsupported browser action: {action}")
