"""Alert generation endpoints: rule sync, batch generation jobs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Annotated

import structlog
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.alert import GenerationJob
from umbrella_ui.db.models.policy import Policy, RiskModel, Rule
from umbrella_ui.deps import get_alert_session, get_es, get_policy_session
from umbrella_ui.es import percolator as perc
from umbrella_ui.schemas.alert import GenerationJobCreate, GenerationJobOut
from umbrella_ui.services.alert_generator import run_generation_job

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/alert-generation", tags=["alert-generation"])


# ---------------------------------------------------------------------------
# Phase 1: Rule sync
# ---------------------------------------------------------------------------


@router.post("/sync-rules", status_code=status.HTTP_200_OK)
async def sync_rules(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    session: Annotated[AsyncSession, Depends(get_policy_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    """Full resync of all active rules to the percolator index.

    Ensures the index exists, then upserts every active rule from an
    active policy under an active risk model.
    """
    await perc.ensure_percolator_index(es)

    stmt = (
        select(Rule, Policy.id.label("policy_id"), RiskModel.id.label("risk_model_id"))
        .join(Policy, Policy.id == Rule.policy_id)
        .join(RiskModel, RiskModel.id == Policy.risk_model_id)
        .where(Rule.is_active == True, Policy.is_active == True, RiskModel.is_active == True)  # noqa: E712
    )
    rows = (await session.execute(stmt)).all()

    upserted = 0
    errors = 0
    for row in rows:
        rule: Rule = row[0]
        try:
            await perc.upsert_rule(
                es,
                rule.id,
                rule.name,
                row.policy_id,
                row.risk_model_id,
                rule.kql,
                rule.severity,
            )
            upserted += 1
        except Exception:
            logger.exception("sync_rules_upsert_failed", rule_id=str(rule.id))
            errors += 1

    logger.info("sync_rules_complete", upserted=upserted, errors=errors)
    return {"upserted": upserted, "errors": errors}


# ---------------------------------------------------------------------------
# Phase 2: Batch generation jobs
# ---------------------------------------------------------------------------


@router.get("/default-query", status_code=status.HTTP_200_OK)
async def get_default_query(
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
) -> dict:
    """Return the default KQL that would be used for a new generation job."""
    result = await session.execute(
        select(GenerationJob.completed_at)
        .where(GenerationJob.status == "completed")
        .order_by(GenerationJob.completed_at.desc())
        .limit(1)
    )
    last_completed_at = result.scalar_one_or_none()
    if last_completed_at:
        iso = last_completed_at.isoformat()
        default_kql = f'@timestamp >= "{iso}"'
    else:
        default_kql = "*"
    return {"default_kql": default_kql}


@router.get("/jobs", response_model=list[GenerationJobOut])
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
) -> list[GenerationJob]:
    result = await session.execute(
        select(GenerationJob)
        .order_by(GenerationJob.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.get("/jobs/{job_id}", response_model=GenerationJobOut)
async def get_job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
) -> GenerationJob:
    result = await session.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job


@router.post("/jobs", response_model=GenerationJobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    body: GenerationJobCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    current_user: Annotated[dict, Depends(require_role("supervisor"))],
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
) -> GenerationJob:
    """Create and start a batch alert generation job."""
    # Mark any stale pending/running jobs (older than 10 minutes) as failed first.
    # This cleans up jobs that got stuck due to a crash before our error handling ran.
    stale_cutoff = datetime.utcnow() - timedelta(minutes=10)
    stale_result = await session.execute(
        select(GenerationJob).where(
            GenerationJob.status.in_(["pending", "running"]),
            GenerationJob.created_at < stale_cutoff,
        )
    )
    stale_jobs = stale_result.scalars().all()
    for stale_job in stale_jobs:
        stale_job.status = "failed"
        stale_job.error_message = "Job timed out — marked failed automatically"
        stale_job.completed_at = datetime.utcnow()
        logger.warning("generation_job_stale_cleaned_up", job_id=str(stale_job.id))
    if stale_jobs:
        await session.commit()

    # Concurrency guard: reject if a non-stale pending/running job exists
    existing = await session.execute(
        select(GenerationJob)
        .where(GenerationJob.status.in_(["pending", "running"]))
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A generation job is already pending or running",
        )

    # Create job row
    job = GenerationJob(
        scope_type=body.scope_type,
        scope_ids=body.scope_ids,
        query_kql=body.query_kql,
        created_by=current_user["id"],
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Get session factories from app state
    db = request.app.state.db

    # Fire background task
    asyncio.create_task(
        run_generation_job(
            job_id=job.id,
            alert_session_factory=db.alert_session,
            policy_session_factory=db.policy_session,
            es=es,
        ),
        name=f"generation_job_{job.id}",
    )

    logger.info("generation_job_created", job_id=str(job.id), scope_type=body.scope_type)
    return job
