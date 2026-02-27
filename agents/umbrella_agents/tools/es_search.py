"""Elasticsearch search tool for LangChain agents.

Supports full-text search with field selection (to minimize token usage)
and aggregations (e.g. term counts on sender, channel, etc.).
"""

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

    query: str = Field(description="Search query text. Use '*' to match all documents.")
    index: str = Field(
        default="messages-*",
        description="Elasticsearch index pattern to search",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Term/range filters as {field: value} or {field: {gte: ..., lte: ...}}. "
            "Example: {\"channel\": \"email\", \"timestamp\": {\"gte\": \"now-7d\"}}"
        ),
    )
    fields: list[str] | None = Field(
        default=None,
        description=(
            "List of fields to return from each document. "
            "When null, returns all fields. Set this to reduce response size. "
            "Example: [\"body_text\", \"channel\", \"timestamp\", \"participants.name\"]"
        ),
    )
    aggs: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Elasticsearch aggregations to run. "
            "Example: {\"by_channel\": {\"terms\": {\"field\": \"channel\", \"size\": 10}}, "
            "\"by_sender\": {\"terms\": {\"field\": \"participants.name.keyword\", \"size\": 10}}, "
            "\"over_time\": {\"date_histogram\": {\"field\": \"timestamp\", \"calendar_interval\": \"month\"}}} "
            "When aggregations are provided, set size=0 to skip returning documents and save tokens."
        ),
    )
    size: int = Field(default=10, description="Number of documents to return (0 for aggregation-only)", ge=0, le=100)


class ESSearchTool(BaseTool):
    """Full-text search and aggregation across Elasticsearch indices.

    Returns matching documents (with optional field selection) and/or
    aggregation results.  Scoped to the agent's allowed index patterns.
    """

    name: str = "es_search"
    description: str = (
        "Search Elasticsearch for documents and/or run aggregations. "
        "Use 'fields' to request only the fields you need (saves tokens). "
        "Use 'aggs' with size=0 for counts/stats without fetching documents. "
        "Use 'filters' for term and range filtering."
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
        fields: list[str] | None = None,
        aggs: dict[str, Any] | None = None,
        size: int = 10,
    ) -> str:
        if not self._validate_index(index):
            return json.dumps({
                "error": f"Access denied: index '{index}' is not in the allowed list",
            })

        # Build query
        if query == "*":
            query_clause: dict[str, Any] = {"match_all": {}}
        else:
            query_clause = {"multi_match": {
                "query": query,
                "fields": ["body_text", "transcript", "translated_text", "subject"],
                "type": "best_fields",
            }}

        filter_clauses = []
        for field_name, value in (filters or {}).items():
            if isinstance(value, dict):
                filter_clauses.append({"range": {field_name: value}})
            else:
                filter_clauses.append({"term": {field_name: value}})

        if filter_clauses:
            es_query: dict[str, Any] = {"bool": {"must": [query_clause], "filter": filter_clauses}}
        else:
            es_query = query_clause

        # Build request kwargs using the official client API
        search_kwargs: dict[str, Any] = {
            "index": index,
            "query": es_query,
            "size": size,
            "sort": [{"timestamp": {"order": "desc", "unmapped_type": "date"}}],
        }

        # Field selection — only return requested fields
        if fields is not None:
            search_kwargs["source"] = fields

        # Highlights only when returning documents
        if size > 0 and query != "*":
            search_kwargs["highlight"] = {
                "fields": {
                    "body_text": {"fragment_size": 150, "number_of_fragments": 1},
                    "transcript": {"fragment_size": 150, "number_of_fragments": 1},
                    "translated_text": {"fragment_size": 150, "number_of_fragments": 1},
                },
            }

        # Aggregations
        if aggs:
            search_kwargs["aggs"] = aggs

        try:
            resp = await self.es_client.search(**search_kwargs)
        except Exception as exc:
            logger.error("es_search_error", error=str(exc))
            return json.dumps({"error": f"Search failed: {exc}"})

        # Parse response
        result: dict[str, Any] = {}

        # Hits
        hits = resp.get("hits", {})
        result["total"] = hits.get("total", {}).get("value", 0)

        if size > 0:
            docs = []
            for hit in hits.get("hits", []):
                doc: dict[str, Any] = {
                    "id": hit["_id"],
                    "score": hit.get("_score"),
                    "source": hit["_source"],
                }
                if hit.get("highlight"):
                    doc["highlights"] = hit["highlight"]
                docs.append(doc)
            result["results"] = docs

        # Aggregations
        if aggs and "aggregations" in resp:
            result["aggregations"] = resp["aggregations"]

        return json.dumps(result, default=str)


# Register with global registry
registry.register("es_search", ESSearchTool)
