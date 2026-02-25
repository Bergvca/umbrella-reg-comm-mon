"""Read-only SQL query tool for LangChain agents."""

from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy import text

from umbrella_agents.tools.registry import registry

logger = structlog.get_logger()

# SQL keywords that indicate write operations
_WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "VACUUM", "REINDEX",
}


class SQLQueryInput(BaseModel):
    """Input schema for the sql_query tool."""

    query: str = Field(description="SQL SELECT query to execute")


class SQLQueryTool(BaseTool):
    """Execute read-only SQL queries against PostgreSQL.

    Queries are scoped to the agent's allowed schemas using
    ``SET search_path``. Only SELECT statements are allowed.
    """

    name: str = "sql_query"
    description: str = (
        "Execute a read-only SQL query against the PostgreSQL database. "
        "Only SELECT statements are allowed. Use this to look up structured "
        "data like entities, alerts, reviews, or agent run history."
    )
    args_schema: type[BaseModel] = SQLQueryInput

    scope: Any  # DataSourceScope
    es_client: Any = None  # Not used but kept for uniform interface
    session_factory: Any  # async_sessionmaker
    tool_config: dict = {}

    def _validate_query(self, query: str) -> str | None:
        """Return error message if query is unsafe, else None."""
        normalized = query.strip().upper()

        # Must start with SELECT or WITH (CTE)
        if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
            return "Only SELECT queries are allowed"

        # Check for write keywords anywhere in the query
        tokens = set(normalized.split())
        forbidden = tokens & _WRITE_KEYWORDS
        if forbidden:
            return f"Query contains forbidden keywords: {', '.join(forbidden)}"

        # Block semicolons (no multi-statement)
        if ";" in query.rstrip().rstrip(";"):
            return "Multi-statement queries are not allowed"

        return None

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, query: str) -> str:
        error = self._validate_query(query)
        if error:
            return json.dumps({"error": error})

        if not self.scope.allowed_pg_schemas:
            return json.dumps({"error": "No PostgreSQL schemas are allowed for this agent"})

        search_path = ", ".join(self.scope.allowed_pg_schemas)

        try:
            async with self.session_factory() as session:
                # Set search_path to allowed schemas + ensure read-only transaction
                await session.execute(text(f"SET search_path TO {search_path}"))
                await session.execute(text("SET TRANSACTION READ ONLY"))

                result = await session.execute(text(query))
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                return json.dumps({
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                }, default=str)

        except Exception as exc:
            logger.error("sql_query_error", error=str(exc))
            return json.dumps({"error": f"Query failed: {exc}"})


# Register with global registry
registry.register("sql_query", SQLQueryTool)
