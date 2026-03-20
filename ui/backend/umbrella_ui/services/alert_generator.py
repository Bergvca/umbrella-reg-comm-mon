"""Batch alert generation engine.

Runs as an asyncio background task (via asyncio.create_task).
Queries ES for each active rule in scope, inserts matching alerts into PG.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from logging import Logger
from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from umbrella_ui.db.models.alert import GenerationJob
from umbrella_ui.db.models.alert import Alert
from umbrella_ui.db.models.policy import Policy, RiskModel, Rule

logger = structlog.get_logger()

_PIT_KEEP_ALIVE = "2m"
_PAGE_SIZE = 500


async def _resolve_kql(job: GenerationJob, alert_session: AsyncSession) -> str:
    """Return the effective KQL for a job (resolving NULL to 'since last run')."""
    if job.query_kql:
        return job.query_kql

    # Find the most recent completed job (other than this one)
    result = await alert_session.execute(
        select(GenerationJob.completed_at)
        .where(
            GenerationJob.status == "completed",
            GenerationJob.id != job.id,
        )
        .order_by(GenerationJob.completed_at.desc())
        .limit(1)
    )
    last_completed_at = result.scalar_one_or_none()
    if last_completed_at:
        iso = last_completed_at.isoformat()
        return f'@timestamp >= "{iso}"'
    return "*"


async def _resolve_rules(
    job: GenerationJob, policy_session: AsyncSession
) -> list[dict[str, Any]]:
    """Return active rules in scope as list of dicts."""
    stmt = (
        select(Rule.id, Rule.name, Rule.kql, Rule.severity, Policy.id.label("policy_id"))
        .join(Policy, Policy.id == Rule.policy_id)
        .where(Rule.is_active == True, Policy.is_active == True)  # noqa: E712
    )
    if job.scope_type == "policies":
        stmt = stmt.where(Policy.id.in_(job.scope_ids or []))
    elif job.scope_type == "risk_models":
        stmt = stmt.join(RiskModel, RiskModel.id == Policy.risk_model_id).where(
            RiskModel.id.in_(job.scope_ids or [])
        )

    rows = (await policy_session.execute(stmt)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "kql": row.kql,
            "severity": row.severity,
            "policy_id": row.policy_id,
        }
        for row in rows
    ]


async def _search_es_with_pit(
    es: AsyncElasticsearch,
    rule_kql: str,
    scope_kql: str,
) -> list[dict[str, Any]]:
    """Use PIT + search_after to iterate all matching ES documents.

    Returns a list of {es_index, es_document_id, es_document_ts} dicts.
    """
    # Open a PIT
    pit_resp = await es.open_point_in_time(
        index="messages-*,trades-*", keep_alive=_PIT_KEEP_ALIVE
    )
    pit_id = pit_resp["id"]

    hits: list[dict[str, Any]] = []
    search_after = None

    try:
        while True:
            body: dict[str, Any] = {
                "size": _PAGE_SIZE,
                "query": {
                    "bool": {
                        "must": [
                            {"query_string": {"query": rule_kql, "default_field": "body_text"}},
                            {"query_string": {"query": scope_kql, "default_field": "body_text"}},
                        ]
                    }
                },
                "sort": [{"@timestamp": "asc"}, {"_shard_doc": "asc"}],
                "pit": {"id": pit_id, "keep_alive": _PIT_KEEP_ALIVE},
            }
            if search_after:
                body["search_after"] = search_after

            resp = await es.search(body=body)
            page_hits = resp["hits"]["hits"]
            if not page_hits:
                break

            for hit in page_hits:
                # Extract entity_ids from participants for alert-entity linking
                entity_ids: list[str] = []
                for p in hit["_source"].get("participants") or []:
                    eid = p.get("entity_id")
                    if eid:
                        entity_ids.append(eid)
                hits.append({
                    "es_index": hit["_index"],
                    "es_document_id": hit["_id"],
                    "es_document_ts": hit["_source"].get("@timestamp"),
                    "channel": hit["_source"].get("channel", "unknown"),
                    "entity_ids": list(set(entity_ids)),
                })
            search_after = page_hits[-1]["sort"]

            if len(page_hits) < _PAGE_SIZE:
                break
    finally:
        try:
            await es.close_point_in_time(body={"id": pit_id})
        except Exception:
            pass

    return hits


async def run_generation_job(
    job_id: uuid.UUID,
    alert_session_factory: async_sessionmaker[AsyncSession],
    policy_session_factory: async_sessionmaker[AsyncSession],
    es: AsyncElasticsearch,
) -> None:
    """Core batch generation logic. Called as asyncio.create_task."""
    log = logger.bind(job_id=str(job_id))
    log.info("generation_job_started")

    try:
        await _run_generation_job_inner(
            job_id, alert_session_factory, policy_session_factory, es, log
        )
    except Exception as exc:
        # Last-resort handler: task crashed before/outside the inner try/except.
        # Open a fresh session to mark the job failed so it doesn't stay 'pending'.
        log.exception("generation_job_unhandled_error")
        try:
            async with alert_session_factory() as recovery_session:
                result = await recovery_session.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job and job.status in ("pending", "running"):
                    job.status = "failed"
                    job.error_message = f"Unhandled error: {exc}"
                    job.completed_at = datetime.utcnow()
                    await recovery_session.commit()
        except Exception:
            log.exception("generation_job_recovery_failed")


async def _run_generation_job_inner(
    job_id: uuid.UUID,
    alert_session_factory: async_sessionmaker[AsyncSession],
    policy_session_factory: async_sessionmaker[AsyncSession],
    es: AsyncElasticsearch,
    log: Any,
) -> None:
    async with alert_session_factory() as alert_session:
        # 1. Load job, mark running
        result = await alert_session.execute(
            select(GenerationJob).where(GenerationJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            log.error("generation_job_not_found")
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        await alert_session.commit()
        await alert_session.refresh(job)

        try:
            # 2. Resolve KQL
            resolved_kql = await _resolve_kql(job, alert_session)
            job.query_kql_resolved = resolved_kql
            await alert_session.commit()

            # 3. Resolve rules
            async with policy_session_factory() as policy_session:
                rules = await _resolve_rules(job, policy_session)

            log.info("generation_job_rules_resolved", rule_count=len(rules))
            total_alerts = 0
            total_docs = 0

            # 4. For each rule, search ES + insert alerts
            for rule in rules:
                try:
                    docs = await _search_es_with_pit(es, rule["kql"], resolved_kql)
                except Exception:
                    log.exception("generation_job_es_search_failed", rule_id=str(rule["id"]))
                    continue

                total_docs += len(docs)

                for doc in docs:
                    # Parse timestamp if string; strip tzinfo because the DB
                    # column is TIMESTAMP WITHOUT TIME ZONE.
                    doc_ts: datetime | None = None
                    raw_ts = doc.get("es_document_ts")
                    if isinstance(raw_ts, str):
                        try:
                            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                            doc_ts = dt.replace(tzinfo=None)
                        except ValueError:
                            pass
                    elif isinstance(raw_ts, datetime):
                        doc_ts = raw_ts.replace(tzinfo=None)

                    stmt = (
                        pg_insert(Alert)
                        .values(
                            name=rule["name"],
                            rule_id=rule["id"],
                            es_index=doc["es_index"],
                            es_document_id=doc["es_document_id"],
                            es_document_ts=doc_ts,
                            channel=doc.get("channel", "unknown"),
                            severity=rule["severity"],
                        )
                        .on_conflict_do_nothing(
                            index_elements=["rule_id", "es_document_id"]
                        )
                    )
                    result = await alert_session.execute(stmt)
                    if result.rowcount:
                        total_alerts += 1
                        # Link alert to entities found in the document's participants
                        if doc.get("entity_ids"):
                            # Retrieve the alert id (inserted row)
                            alert_row = (await alert_session.execute(
                                select(Alert.id).where(
                                    Alert.rule_id == rule["id"],
                                    Alert.es_document_id == doc["es_document_id"],
                                )
                            )).scalar_one_or_none()
                            if alert_row:
                                for eid in doc["entity_ids"]:
                                    try:
                                        await alert_session.execute(
                                            text(
                                                "INSERT INTO alert.alert_entities (alert_id, entity_id) "
                                                "VALUES (:alert_id, :entity_id) ON CONFLICT DO NOTHING"
                                            ),
                                            {"alert_id": alert_row, "entity_id": eid},
                                        )
                                    except Exception:
                                        log.warning(
                                            "alert_entity_link_failed",
                                            alert_id=str(alert_row),
                                            entity_id=eid,
                                            exc_info=True,
                                        )

                job.rules_evaluated += 1
                job.alerts_created = total_alerts
                job.documents_scanned = total_docs
                await alert_session.commit()

            # 5. Mark completed
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.alerts_created = total_alerts
            job.documents_scanned = total_docs
            await alert_session.commit()

            log.info(
                "generation_job_completed",
                alerts_created=total_alerts,
                rules_evaluated=len(rules),
                documents_scanned=total_docs,
            )

        except Exception as exc:
            log.exception("generation_job_failed")
            try:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.utcnow()
                await alert_session.commit()
            except Exception:
                log.exception("generation_job_status_update_failed")
                raise
