"""Tool registry — maps tool names to LangChain tool implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool


@dataclass
class DataSourceScope:
    """Defines which data sources an agent is allowed to access."""

    allowed_es_indices: list[str] = field(default_factory=list)
    allowed_pg_schemas: list[str] = field(default_factory=list)


class ToolRegistry:
    """Maps tool names to factory functions that produce scoped LangChain tools."""

    def __init__(self) -> None:
        self._factories: dict[str, type] = {}

    def register(self, name: str, tool_class: type) -> None:
        self._factories[name] = tool_class

    def build_tools(
        self,
        tool_names: list[str],
        scope: DataSourceScope,
        es_client: Any,
        session_factory: Any,
        tool_configs: dict[str, dict] | None = None,
    ) -> list[BaseTool]:
        """Build scoped tool instances for the given tool names."""
        tools: list[BaseTool] = []
        configs = tool_configs or {}
        for name in tool_names:
            if name not in self._factories:
                continue
            tool_cls = self._factories[name]
            tool = tool_cls(
                scope=scope,
                es_client=es_client,
                session_factory=session_factory,
                tool_config=configs.get(name, {}),
            )
            tools.append(tool)
        return tools


# Global registry instance
registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return registry
