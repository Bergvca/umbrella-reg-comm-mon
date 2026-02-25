"""Ingest-time percolation — match normalized messages against alert rules.

After a message is indexed into Elasticsearch (via Logstash), this module
percolates the document against the ``umbrella-alert-rules`` index to find
matching rules, then inserts alerts into PostgreSQL.

Lifecycle mirrors EntityResolver: call start() at service startup, stop() on
shutdown.  The fail-open design means any exception during percolation is
logged but does not abort message processing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import structlog
from elasticsearch import AsyncElasticsearch

from .config import AlertDBConfig, ElasticsearchConfig

logger = structlog.get_logger()

_INSERT_ALERT = """
    INSERT INTO alert.alerts (name, rule_id, es_index, es_document_id, es_document_ts, severity)
    VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (rule_id, es_document_id) DO NOTHING
"""


class AlertPercolator:
    """Percolate messages against registered alert rules and write alerts to PG."""

    def __init__(
        self,
        es_config: ElasticsearchConfig,
        alert_db_config: AlertDBConfig,
    ) -> None:
        self._es_config = es_config
        self._alert_db_config = alert_db_config
        self._es: AsyncElasticsearch | None = None
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        """Create ES client and PG connection pool."""
        self._es = AsyncElasticsearch(
            hosts=[self._es_config.url],
            request_timeout=self._es_config.request_timeout,
        )
        if self._alert_db_config.dsn:
            self._pool = await asyncpg.create_pool(
                self._alert_db_config.dsn, min_size=1, max_size=3
            )
        logger.info(
            "alert_percolator_started",
            es_url=self._es_config.url,
            pg_enabled=self._pool is not None,
        )

    async def stop(self) -> None:
        """Close ES client and PG pool."""
        if self._es:
            await self._es.close()
        if self._pool:
            await self._pool.close()
        logger.info("alert_percolator_stopped")

    async def percolate(
        self,
        message_id: str,
        es_index: str,
        document: dict,
        document_ts: datetime | None,
    ) -> int:
        """Percolate a document against the alert rules index.

        Inserts one ``alert.alerts`` row per matching rule (idempotent).
        Returns the number of new alerts created.
        Fails open — any exception is logged and 0 is returned.
        """
        if not self._es or not self._pool:
            return 0

        try:
            resp = await self._es.search(
                index=self._es_config.percolator_index,
                body={
                    "query": {
                        "percolate": {
                            "field": "query",
                            "document": document,
                        }
                    }
                },
            )
        except Exception:
            logger.exception(
                "percolation_es_failed",
                message_id=message_id,
            )
            return 0

        hits = resp["hits"]["hits"]
        if not hits:
            return 0

        created = 0
        async with self._pool.acquire() as conn:
            for hit in hits:
                src = hit["_source"]
                rule_id_str = src.get("rule_id")
                rule_name = src.get("rule_name", "")
                severity = src.get("severity", "medium")

                if not rule_id_str:
                    continue

                try:
                    rule_id = UUID(rule_id_str)
                except ValueError:
                    continue

                ts = document_ts
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                result = await conn.execute(
                    _INSERT_ALERT,
                    rule_name,
                    rule_id,
                    es_index,
                    message_id,
                    ts,
                    severity,
                )
                # result is a status tag like "INSERT 0 1" or "INSERT 0 0"
                if result.endswith(" 1"):
                    created += 1

        if created:
            logger.info(
                "alerts_created_via_percolation",
                message_id=message_id,
                alerts_created=created,
            )
        return created
