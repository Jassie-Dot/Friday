from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError
