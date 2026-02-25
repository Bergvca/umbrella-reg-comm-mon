"""Elasticsearch full-text search tool for LangChain agents."""

from __future__ import annotations

import json
from fnmatch import fnmatch
from typing import Any

import structlog
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from umbrella_agents.tools.registry import registry

logger = structlog.get_logger()


class ESSearchInput(BaseModel):
    """Input schema for the es_search tool."""

    query: str = Field(description="Search query text")
    index: str = Field(
        default="messages-*",
        description="Elasticsearch index pattern to search",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional term/range filters as {field: value} or {field: {gte: ..., lte: ...}}",
    )
    size: int = Field(default=10, description="Number of results to return", ge=1, le=100)


class ESSearchTool(BaseTool):
    """Full-text search across Elasticsearch indices.

    Returns matching documents with highlights. Scoped to the agent's
    allowed index patterns.
    """

    name: str = "es_search"
    description: str = (
        "Search for documents in Elasticsearch using full-text queries. "
        "Use this to find messages, communications, or any indexed content. "
        "Returns matching documents with highlighted snippets."
    )
    args_schema: type[BaseModel] = ESSearchInput

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

    async def _arun(
        self,
        query: str,
        index: str = "messages-*",
        filters: dict[str, Any] | None = None,
        size: int = 10,
    ) -> str:
        if not self._validate_index(index):
            return json.dumps({
                "error": f"Access denied: index '{index}' is not in the allowed list",
            })

        must = [{"multi_match": {
            "query": query,
            "fields": ["body_text", "transcript", "translated_text", "subject"],
            "type": "best_fields",
        }}]

        filter_clauses = []
        for field_name, value in (filters or {}).items():
            if isinstance(value, dict):
                filter_clauses.append({"range": {field_name: value}})
            else:
                filter_clauses.append({"term": {field_name: value}})

        body: dict[str, Any] = {
            "query": {"bool": {"must": must, "filter": filter_clauses}},
            "highlight": {
                "fields": {
                    "body_text": {"fragment_size": 200, "number_of_fragments": 2},
                    "transcript": {"fragment_size": 200, "number_of_fragments": 2},
                    "translated_text": {"fragment_size": 200, "number_of_fragments": 2},
                },
            },
            "size": size,
            "sort": [{"timestamp": {"order": "desc", "unmapped_type": "date"}}],
        }

        try:
            resp = await self.es_client.search(index=index, body=body)
        except Exception as exc:
            logger.error("es_search_error", error=str(exc))
            return json.dumps({"error": f"Search failed: {exc}"})

        hits = resp.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = []
        for hit in hits.get("hits", []):
            results.append({
                "id": hit["_id"],
                "index": hit["_index"],
                "score": hit.get("_score"),
                "source": hit["_source"],
                "highlights": hit.get("highlight", {}),
            })

        return json.dumps({"total": total, "results": results}, default=str)


# Register with global registry
registry.register("es_search", ESSearchTool)
