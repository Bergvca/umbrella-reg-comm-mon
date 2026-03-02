"""Elasticsearch index mapping discovery tool for LangChain agents."""

from __future__ import annotations

import json
from fnmatch import fnmatch
from typing import Any

import structlog
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from umbrella_agents.tools.registry import registry

logger = structlog.get_logger()


class ESGetMappingInput(BaseModel):
    """Input schema for the es_get_mapping tool."""

    index: str = Field(
        default="messages-*",
        description="Elasticsearch index pattern to get the mapping for",
    )


class ESGetMappingTool(BaseTool):
    """Retrieve the field mapping of an Elasticsearch index.

    Returns the field names, types, and structure so the agent knows
    which fields are available for searching and filtering.
    """

    name: str = "es_get_mapping"
    description: str = (
        "Get the field mapping (schema) of an Elasticsearch index. "
        "Use this BEFORE searching to discover available fields, their types, "
        "and how to filter on them. Returns field names and Elasticsearch types."
    )
    args_schema: type[BaseModel] = ESGetMappingInput

    scope: Any  # DataSourceScope
    es_client: Any  # AsyncElasticsearch
    session_factory: Any  # async_sessionmaker
    tool_config: dict = {}

    def _validate_index(self, index: str) -> bool:
        """Check if the requested index matches any allowed pattern."""
        for allowed in self.scope.allowed_es_indices:
            if fnmatch(index, allowed) or fnmatch(allowed, index):
                return True
        return False

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, index: str = "messages-*") -> str:
        if not self._validate_index(index):
            return json.dumps({
                "error": f"Access denied: index '{index}' is not in the allowed list",
            })

        try:
            resp = await self.es_client.indices.get_mapping(index=index)
        except Exception as exc:
            logger.error("es_get_mapping_error", error=str(exc))
            return json.dumps({"error": f"Failed to get mapping: {exc}"})

        # Flatten mappings from all matching indices into a single field list.
        fields: dict[str, str] = {}
        for index_name, index_data in resp.items():
            properties = (
                index_data.get("mappings", {}).get("properties", {})
            )
            _flatten_properties(properties, "", fields)

        return json.dumps({
            "index": index,
            "fields": fields,
            "field_count": len(fields),
        }, default=str)


def _flatten_properties(
    properties: dict, prefix: str, out: dict[str, str],
) -> None:
    """Recursively flatten nested ES mapping properties into dotted field names."""
    for name, meta in properties.items():
        full_name = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        field_type = meta.get("type")
        if field_type:
            out[full_name] = field_type
        # Recurse into nested/object properties
        if "properties" in meta:
            _flatten_properties(meta["properties"], full_name, out)


# Register with global registry
registry.register("es_get_mapping", ESGetMappingTool)
