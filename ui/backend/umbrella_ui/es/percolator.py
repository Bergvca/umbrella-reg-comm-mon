"""Percolator index helpers for alert rule syncing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError

logger = structlog.get_logger()

PERCOLATOR_INDEX = "umbrella-alert-rules"

_MAPPING_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / \
    "infrastructure" / "elasticsearch" / "umbrella-alert-rules-mapping.json"


def _load_mapping() -> dict:
    """Load the percolator index mapping from the JSON file."""
    # Try relative to the repo root
    candidates = [
        _MAPPING_PATH,
        Path("/app/infrastructure/elasticsearch/umbrella-alert-rules-mapping.json"),
    ]
    # Also try env override
    env_path = os.environ.get("PERCOLATOR_MAPPING_PATH")
    if env_path:
        candidates.insert(0, Path(env_path))

    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())

    # Inline fallback if mapping file not found
    return {
        "mappings": {
            "properties": {
                "query":         {"type": "percolator"},
                "rule_id":       {"type": "keyword"},
                "rule_name":     {"type": "keyword"},
                "policy_id":     {"type": "keyword"},
                "risk_model_id": {"type": "keyword"},
                "severity":      {"type": "keyword"},
                "message_id":    {"type": "keyword"},
                "channel":       {"type": "keyword"},
                "direction":     {"type": "keyword"},
                "timestamp":     {"type": "date"},
                "body_text":     {"type": "text", "analyzer": "standard"},
                "participants": {
                    "type": "nested",
                    "properties": {
                        "id":   {"type": "keyword"},
                        "name": {"type": "text"},
                        "role": {"type": "keyword"},
                    },
                },
                "metadata": {
                    "properties": {
                        "subject": {"type": "text"},
                    }
                },
            }
        }
    }


async def ensure_percolator_index(es: AsyncElasticsearch) -> None:
    """Create the percolator index if it doesn't already exist."""
    exists = await es.indices.exists(index=PERCOLATOR_INDEX)
    if exists.body:
        return
    mapping = _load_mapping()
    try:
        await es.indices.create(index=PERCOLATOR_INDEX, body=mapping)
        logger.info("percolator_index_created", index=PERCOLATOR_INDEX)
    except Exception as exc:
        # 400 = already exists (race condition) — ignore
        if hasattr(exc, "status_code") and exc.status_code == 400:
            pass
        else:
            logger.warning("percolator_index_create_failed", error=str(exc))


def _rule_to_percolator_doc(
    rule_id: UUID,
    rule_name: str,
    policy_id: UUID,
    risk_model_id: UUID,
    kql: str,
    severity: str,
) -> dict:
    """Build a percolator document from a rule."""
    return {
        "rule_id":       str(rule_id),
        "rule_name":     rule_name,
        "policy_id":     str(policy_id),
        "risk_model_id": str(risk_model_id),
        "severity":      severity,
        "query": {
            "query_string": {
                "query":         kql,
                "default_field": "body_text",
            }
        },
    }


async def upsert_rule(
    es: AsyncElasticsearch,
    rule_id: UUID,
    rule_name: str,
    policy_id: UUID,
    risk_model_id: UUID,
    kql: str,
    severity: str,
) -> None:
    """Index (upsert) a rule into the percolator index."""
    doc = _rule_to_percolator_doc(rule_id, rule_name, policy_id, risk_model_id, kql, severity)
    await es.index(index=PERCOLATOR_INDEX, id=str(rule_id), document=doc)
    logger.info("percolator_rule_upserted", rule_id=str(rule_id))


async def delete_rule(es: AsyncElasticsearch, rule_id: UUID) -> None:
    """Remove a rule from the percolator index (ignores 404)."""
    try:
        await es.delete(index=PERCOLATOR_INDEX, id=str(rule_id))
        logger.info("percolator_rule_deleted", rule_id=str(rule_id))
    except NotFoundError:
        pass
    except Exception:
        logger.exception("percolator_rule_delete_failed", rule_id=str(rule_id))
