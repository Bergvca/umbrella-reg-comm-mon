"""LiteLLM integration for model-agnostic LLM calls."""

from __future__ import annotations

import json

import structlog
from litellm import acompletion

from umbrella_agents.tool_call_parser import _strip_think_tags

logger = structlog.get_logger()

TRANSLATE_SYSTEM_PROMPT = """\
You are an Elasticsearch query translator. You convert natural language search \
queries into valid Elasticsearch query DSL JSON.

You are given:
1. A natural language query from the user.
2. An Elasticsearch field schema describing available fields and their types.

Your job:
- Produce a valid Elasticsearch query DSL body (the value of the "query" key in a search request).
- Map temporal expressions ("last week", "yesterday", "past 3 months") to ES range \
filters using relative date math (now-1w, now-1d, now-3M, etc.).
- Map channel references ("emails", "Teams chats", "calls") to term filters on the \
"channel" field.
- Map participant references to nested participants queries where applicable.
- Map sentiment references ("positive", "negative") to term filters on the "sentiment" field.
- Use multi_match on text fields (body_text, transcript, translated_text) for content queries.
- Always include highlighting on text fields that appear in the query.
- Sort by timestamp descending by default.
- Never fabricate field names — only use fields from the provided schema.
- Never include "from" or "size" — the caller injects pagination.

Respond with ONLY a JSON object containing two keys:
- "es_query": the Elasticsearch query DSL body (dict)
- "explanation": a short human-readable summary of how you interpreted the query

No markdown fences, no extra text — just the JSON object.\
"""


async def translate_nl_to_es_query(
    query: str,
    field_schema: dict[str, str],
    *,
    model: str = "openai/gpt-4o",
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict:
    """Translate a natural language query to Elasticsearch query DSL.

    Uses LiteLLM for model-agnostic LLM calls.

    Returns:
        dict with keys ``es_query`` (dict) and ``explanation`` (str).
    """
    user_message = (
        f"Natural language query: {query}\n\n"
        f"Field schema:\n{json.dumps(field_schema, indent=2)}"
    )

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    logger.info("translate_query_start", model=model, query=query)

    response = await acompletion(**kwargs)
    content = response.choices[0].message.content or ""

    # Reasoning models (e.g. DeepSeek-V3) emit a <think>...</think> block
    # before the actual JSON output.  Strip it so json.loads doesn't choke.
    content = _strip_think_tags(content)

    result = json.loads(content)

    if "es_query" not in result:
        raise ValueError("LLM response missing 'es_query' key")
    if "explanation" not in result:
        result["explanation"] = ""

    logger.info("translate_query_complete", explanation=result["explanation"])
    return result
