"""Minimal tool contracts used by the humanizer skill.

This module intentionally contains only the data shapes required by the
humanizer handlers.  The host registry may attach richer objects at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(str, Enum):
    EXTERNAL = "external"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    category: ToolCategory
    energy_cost: int = 0
    is_read_only: bool = False
    supports_parallel: bool = False
    optional: bool = False


@dataclass
class ToolContext:
    """General host context; fields are optional for standalone use."""
    registry: Any = None


@dataclass
class ToolExecutionContext(ToolContext):
    """Execution context passed to a tool handler."""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    result: Any = None
    error: str | None = None

    @classmethod
    def success_result(cls, result: Any) -> "ToolResult":
        return cls(ok=True, result=result)

    @classmethod
    def error_result(cls, error: str) -> "ToolResult":
        return cls(ok=False, error=error)


class ToolHandler:
    @property
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    async def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        raise NotImplementedError
