"""Queue management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.alert import Alert
from umbrella_ui.db.models.policy import Rule
from umbrella_ui.db.models.review import Queue, QueueBatch, QueueItem
from umbrella_ui.deps import get_review_session
from umbrella_ui.schemas.alert import AlertOut
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.review import (
    BatchAssign,
    BatchCreate,
    BatchOut,
    BatchStatusUpdate,
    QueueCreate,
    QueueDetail,
    QueueItemCreate,
    QueueItemOut,
    QueueOut,
)

router = APIRouter(prefix="/api/v1", tags=["queues"])


def _batch_out(batch: QueueBatch, item_count: int = 0) -> BatchOut:
    return BatchOut(
        id=batch.id,
        queue_id=batch.queue_id,
        name=batch.name,
        assigned_to=batch.assigned_to,
        assigned_by=batch.assigned_by,
        assigned_at=batch.assigned_at,
        status=batch.status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        item_count=item_count,
    )


@router.get("/queues", response_model=PaginatedResponse[QueueOut])
async def list_queues(
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
    offset: int = 0,
    limit: int = 50,
):
    total = (await session.execute(select(func.count()).select_from(Queue))).scalar_one()
    queues = (
        await session.execute(select(Queue).offset(offset).limit(limit))
    ).scalars().all()
    items = [
        QueueOut(
            id=q.id,
            name=q.name,
            description=q.description,
            policy_id=q.policy_id,
            created_by=q.created_by,
            created_at=q.created_at,
            updated_at=q.updated_at,
        )
        for q in queues
    ]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/queues", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
async def create_queue(
    body: QueueCreate,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    user: Annotated[dict, Depends(require_role("supervisor"))],
):
    queue = Queue(
        name=body.name,
        description=body.description,
        policy_id=body.policy_id,
        created_by=user["id"],
    )
    session.add(queue)
    await session.commit()
    await session.refresh(queue)
    return QueueOut(
        id=queue.id,
        name=queue.name,
        description=queue.description,
        policy_id=queue.policy_id,
        created_by=queue.created_by,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


@router.get("/queues/{queue_id}", response_model=QueueDetail)
async def get_queue(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    queue = (
        await session.execute(select(Queue).where(Queue.id == queue_id))
    ).scalar_one_or_none()
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")

    batch_count = (
        await session.execute(
            select(func.count()).select_from(QueueBatch).where(QueueBatch.queue_id == queue_id)
        )
    ).scalar_one()

    total_items = (
        await session.execute(
            select(func.count())
            .select_from(QueueItem)
            .join(QueueBatch, QueueItem.batch_id == QueueBatch.id)
            .where(QueueBatch.queue_id == queue_id)
        )
    ).scalar_one()

    return QueueDetail(
        id=queue.id,
        name=queue.name,
        description=queue.description,
        policy_id=queue.policy_id,
        created_by=queue.created_by,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
        batch_count=batch_count,
        total_items=total_items,
    )


@router.get("/queues/{queue_id}/batches", response_model=list[BatchOut])
async def list_batches(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    batches = (
        await session.execute(
            select(QueueBatch).where(QueueBatch.queue_id == queue_id).order_by(QueueBatch.created_at)
        )
    ).scalars().all()

    result = []
    for batch in batches:
        item_count = (
            await session.execute(
                select(func.count()).select_from(QueueItem).where(QueueItem.batch_id == batch.id)
            )
        ).scalar_one()
        result.append(_batch_out(batch, item_count))
    return result


@router.post(
    "/queues/{queue_id}/batches",
    response_model=BatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    queue_id: uuid.UUID,
    body: BatchCreate,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    queue = (
        await session.execute(select(Queue).where(Queue.id == queue_id))
    ).scalar_one_or_none()
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")

    batch = QueueBatch(queue_id=queue_id, name=body.name)
    session.add(batch)
    await session.commit()
    await session.refresh(batch)
    return _batch_out(batch)


@router.post(
    "/queues/{queue_id}/generate-batches",
    response_model=list[BatchOut],
    status_code=status.HTTP_201_CREATED,
)
async def generate_batches(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    """Auto-generate batches of 50 alerts for all eligible open alerts."""
    queue = (
        await session.execute(select(Queue).where(Queue.id == queue_id))
    ).scalar_one_or_none()
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")

    # Count existing batches to determine starting batch number
    existing_count = (
        await session.execute(
            select(func.count())
            .select_from(QueueBatch)
            .where(QueueBatch.queue_id == queue_id)
        )
    ).scalar_one()

    # Get IDs of alerts already in any batch of this queue
    already_batched = (
        select(QueueItem.alert_id)
        .join(QueueBatch, QueueItem.batch_id == QueueBatch.id)
        .where(QueueBatch.queue_id == queue_id)
    ).subquery()

    # Query all open alerts whose rule belongs to the queue's policy,
    # excluding alerts already in a batch
    eligible_stmt = (
        select(Alert)
        .join(Rule, Alert.rule_id == Rule.id)
        .where(
            Alert.status == "open",
            Rule.policy_id == queue.policy_id,
            Alert.id.notin_(select(already_batched.c.alert_id)),
        )
        .order_by(Alert.created_at)
    )
    eligible_alerts = (await session.execute(eligible_stmt)).scalars().all()

    if not eligible_alerts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No eligible alerts found",
        )

    # Chunk into groups of 50 and create batches
    batch_size = 50
    created_batches: list[BatchOut] = []
    for i in range(0, len(eligible_alerts), batch_size):
        chunk = eligible_alerts[i : i + batch_size]
        batch_number = existing_count + len(created_batches) + 1
        batch_name = f"{queue.name}-{batch_number:06d}"

        batch = QueueBatch(queue_id=queue_id, name=batch_name)
        session.add(batch)
        await session.flush()

        for pos, alert in enumerate(chunk):
            item = QueueItem(batch_id=batch.id, alert_id=alert.id, position=pos)
            session.add(item)

        created_batches.append(_batch_out(batch, len(chunk)))

    await session.commit()
    return created_batches


@router.get(
    "/queues/{queue_id}/batches/{batch_id}/alerts",
    response_model=list[AlertOut],
)
async def list_batch_alerts(
    queue_id: uuid.UUID,
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Return full alert data for items in a batch, ordered by position."""
    batch = (
        await session.execute(
            select(QueueBatch).where(
                QueueBatch.id == batch_id, QueueBatch.queue_id == queue_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    stmt = (
        select(Alert, Rule.name.label("rule_name"))
        .join(QueueItem, QueueItem.alert_id == Alert.id)
        .join(Rule, Alert.rule_id == Rule.id)
        .where(QueueItem.batch_id == batch_id)
        .order_by(QueueItem.position)
    )
    rows = (await session.execute(stmt)).all()

    return [
        AlertOut(
            id=alert.id,
            name=alert.name,
            rule_id=alert.rule_id,
            es_index=alert.es_index,
            es_document_id=alert.es_document_id,
            es_document_ts=alert.es_document_ts,
            severity=alert.severity,
            status=alert.status,
            created_at=alert.created_at,
            rule_name=rule_name,
        )
        for alert, rule_name in rows
    ]


@router.patch("/queues/{queue_id}/batches/{batch_id}", response_model=BatchOut)
async def update_batch(
    queue_id: uuid.UUID,
    batch_id: uuid.UUID,
    body: BatchAssign | BatchStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    user: Annotated[dict, Depends(require_role("supervisor"))],
):
    batch = (
        await session.execute(
            select(QueueBatch).where(
                QueueBatch.id == batch_id, QueueBatch.queue_id == queue_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if isinstance(body, BatchAssign):
        batch.assigned_to = body.assigned_to
        batch.assigned_by = user["id"]
        batch.assigned_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    else:
        batch.status = body.status

    batch.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    await session.commit()
    await session.refresh(batch)

    item_count = (
        await session.execute(
            select(func.count()).select_from(QueueItem).where(QueueItem.batch_id == batch_id)
        )
    ).scalar_one()
    return _batch_out(batch, item_count)


@router.get("/queues/{queue_id}/batches/{batch_id}/items", response_model=list[QueueItemOut])
async def list_batch_items(
    queue_id: uuid.UUID,
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    batch = (
        await session.execute(
            select(QueueBatch).where(
                QueueBatch.id == batch_id, QueueBatch.queue_id == queue_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    items = (
        await session.execute(
            select(QueueItem).where(QueueItem.batch_id == batch_id).order_by(QueueItem.position)
        )
    ).scalars().all()

    return [
        QueueItemOut(
            id=i.id,
            batch_id=i.batch_id,
            alert_id=i.alert_id,
            position=i.position,
            created_at=i.created_at,
        )
        for i in items
    ]


@router.post(
    "/queues/{queue_id}/batches/{batch_id}/items",
    response_model=QueueItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_item_to_batch(
    queue_id: uuid.UUID,
    batch_id: uuid.UUID,
    body: QueueItemCreate,
    session: Annotated[AsyncSession, Depends(get_review_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    batch = (
        await session.execute(
            select(QueueBatch).where(
                QueueBatch.id == batch_id, QueueBatch.queue_id == queue_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Validate alert exists (review_rw can read alert schema)
    alert = (
        await session.execute(select(Alert).where(Alert.id == body.alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    item = QueueItem(batch_id=batch_id, alert_id=body.alert_id, position=body.position)
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return QueueItemOut(
        id=item.id,
        batch_id=item.batch_id,
        alert_id=item.alert_id,
        position=item.position,
        created_at=item.created_at,
    )


@router.get("/my-queue", response_model=list[BatchOut])
async def my_queue(
    session: Annotated[AsyncSession, Depends(get_review_session)],
    user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Get current user's assigned batches."""
    stmt = (
        select(QueueBatch)
        .where(
            QueueBatch.assigned_to == user["id"],
            QueueBatch.status != "completed",
        )
    )
    batches = (await session.execute(stmt)).scalars().all()

    result = []
    for batch in batches:
        item_count = (
            await session.execute(
                select(func.count())
                .select_from(QueueItem)
                .where(QueueItem.batch_id == batch.id)
            )
        ).scalar_one()
        result.append(_batch_out(batch, item_count))
    return result
