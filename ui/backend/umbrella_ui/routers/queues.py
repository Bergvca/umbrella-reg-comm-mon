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
from umbrella_ui.db.models.review import Queue, QueueBatch, QueueItem
from umbrella_ui.deps import get_review_session
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
        batch.assigned_at = datetime.now(tz=timezone.utc)
    else:
        batch.status = body.status

    batch.updated_at = datetime.now(tz=timezone.utc)
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
