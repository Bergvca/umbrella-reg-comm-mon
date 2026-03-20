"""Entity CRUD + batch upload endpoints."""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from typing import Annotated

import structlog
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.entity import Attribute, Entity, Handle
from umbrella_ui.deps import get_alert_session, get_entity_session, get_es
from umbrella_ui.es.models import ESMessage, ESMessageHit
from umbrella_ui.schemas.alert import AlertOut
from umbrella_ui.schemas.common import PaginatedResponse
from umbrella_ui.schemas.entity import (
    AttributeCreate,
    AttributeOut,
    BatchEntityItem,
    BatchUploadResult,
    EntityCreate,
    EntityOut,
    EntityUpdate,
    HandleCreate,
    HandleOut,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])

_VALID_ENTITY_TYPES = {"person", "organization", "distribution_list"}


def _entity_to_out(entity: Entity) -> EntityOut:
    return EntityOut(
        id=entity.id,
        display_name=entity.display_name,
        entity_type=entity.entity_type,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        created_by=entity.created_by,
        handles=[
            HandleOut(
                id=h.id,
                entity_id=h.entity_id,
                handle_type=h.handle_type,
                handle_value=h.handle_value,
                is_primary=h.is_primary,
                created_at=h.created_at,
            )
            for h in entity.handles
        ],
        attributes=[
            AttributeOut(
                id=a.id,
                entity_id=a.entity_id,
                attr_key=a.attr_key,
                attr_value=a.attr_value,
                valid_from=a.valid_from,
                valid_to=a.valid_to,
                created_at=a.created_at,
            )
            for a in entity.attributes
        ],
    )


# ── List entities ─────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[EntityOut])
async def list_entities(
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    entity_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    attr_key: str | None = Query(default=None),
    attr_value: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    base_stmt = select(Entity)
    if entity_type:
        base_stmt = base_stmt.where(Entity.entity_type == entity_type)
    if search:
        base_stmt = base_stmt.where(Entity.display_name.ilike(f"%{search}%"))
    if attr_key:
        attr_filter = select(Attribute.entity_id).where(Attribute.attr_key == attr_key)
        if attr_value:
            attr_filter = attr_filter.where(Attribute.attr_value.ilike(f"%{attr_value}%"))
        base_stmt = base_stmt.where(Entity.id.in_(attr_filter))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = base_stmt.options(selectinload(Entity.handles), selectinload(Entity.attributes))
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return PaginatedResponse(
        items=[_entity_to_out(e) for e in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


# ── Create entity ────────────────────────────────────────


@router.post("", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(
    body: EntityCreate,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    entity = Entity(
        display_name=body.display_name,
        entity_type=body.entity_type,
        created_by=current_user["id"],
    )
    for h in body.handles:
        entity.handles.append(
            Handle(
                handle_type=h.handle_type,
                handle_value=h.handle_value.lower() if h.handle_type == "email" else h.handle_value,
                is_primary=h.is_primary,
            )
        )
    for a in body.attributes:
        entity.attributes.append(
            Attribute(
                attr_key=a.attr_key,
                attr_value=a.attr_value,
                valid_from=a.valid_from,
                valid_to=a.valid_to,
            )
        )

    session.add(entity)
    try:
        await session.commit()
        await session.refresh(entity, attribute_names=["handles", "attributes"])
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Entity with this display_name and entity_type already exists, or a handle is already assigned.",
        )

    return _entity_to_out(entity)


# ── Get entity ───────────────────────────────────────────


@router.get("/{entity_id}", response_model=EntityOut)
async def get_entity(
    entity_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    stmt = (
        select(Entity)
        .options(selectinload(Entity.handles), selectinload(Entity.attributes))
        .where(Entity.id == entity_id)
    )
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return _entity_to_out(entity)


# ── Entity-linked messages ────────────────────────────────


@router.get("/{entity_id}/messages", response_model=PaginatedResponse[ESMessageHit])
async def get_entity_messages(
    entity_id: uuid.UUID,
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return messages where this entity appears as a participant.

    Searches by participants.entity_id (set at ingestion time) OR by
    matching the entity's handle values against participants.id so that
    messages ingested before the entity existed are still found.
    """
    log = structlog.get_logger()

    # Look up the entity's handle values for fallback matching
    handle_rows = (
        await session.execute(
            select(Handle.handle_value).where(Handle.entity_id == entity_id)
        )
    ).scalars().all()

    # Build nested query: entity_id match OR any handle value match
    entity_id_str = str(entity_id)
    should_clauses: list[dict] = [
        {"term": {"participants.entity_id": entity_id_str}},
    ]
    for hv in handle_rows:
        should_clauses.append({"term": {"participants.id": hv}})

    body = {
        "query": {
            "nested": {
                "path": "participants",
                "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
            }
        },
        "sort": [{"timestamp": "desc"}],
        "from": offset,
        "size": limit,
    }
    try:
        resp = await es.search(index="messages-*", body=body)
    except Exception:
        log.warning("entity_messages_es_error", entity_id=str(entity_id), exc_info=True)
        return PaginatedResponse(items=[], total=0, offset=offset, limit=limit)
    total = resp["hits"]["total"]["value"]
    items = []
    for hit in resp["hits"]["hits"]:
        try:
            msg = ESMessage.model_validate(hit["_source"])
            items.append(ESMessageHit(
                message=msg,
                index=hit["_index"],
                score=hit.get("_score"),
                highlights={},
            ))
        except Exception:
            pass
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


# ── Entity-linked alerts ─────────────────────────────────


@router.get("/{entity_id}/alerts", response_model=list[AlertOut])
async def get_entity_alerts(
    entity_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_alert_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    """Return alerts linked to this entity via alert.alert_entities."""
    sql = text("""
        SELECT a.id, a.name, a.rule_id, a.es_index, a.es_document_id,
               a.es_document_ts, a.severity, a.status, a.created_at,
               r.name AS rule_name, p.name AS policy_name
        FROM alert.alerts a
        JOIN alert.alert_entities ae ON ae.alert_id = a.id
        JOIN policy.rules r ON r.id = a.rule_id
        JOIN policy.policies p ON p.id = r.policy_id
        WHERE ae.entity_id = :entity_id
        ORDER BY a.created_at DESC
    """)
    result = await session.execute(sql, {"entity_id": entity_id})
    return [
        AlertOut(
            id=row.id,
            name=row.name,
            rule_id=row.rule_id,
            rule_name=row.rule_name,
            policy_name=row.policy_name,
            es_index=row.es_index,
            es_document_id=row.es_document_id,
            es_document_ts=row.es_document_ts,
            severity=row.severity,
            status=row.status,
            created_at=row.created_at,
        )
        for row in result.all()
    ]


# ── Update entity ────────────────────────────────────────


@router.patch("/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: uuid.UUID,
    body: EntityUpdate,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    stmt = (
        select(Entity)
        .options(selectinload(Entity.handles), selectinload(Entity.attributes))
        .where(Entity.id == entity_id)
    )
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    if body.display_name is not None:
        entity.display_name = body.display_name
    if body.entity_type is not None:
        entity.entity_type = body.entity_type

    try:
        await session.commit()
        await session.refresh(entity, attribute_names=["handles", "attributes"])
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate display_name + entity_type")

    return _entity_to_out(entity)


# ── Delete entity ────────────────────────────────────────


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    entity = (await session.execute(select(Entity).where(Entity.id == entity_id))).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    await session.delete(entity)
    await session.commit()


# ── Handle CRUD ──────────────────────────────────────────


@router.post("/{entity_id}/handles", response_model=HandleOut, status_code=status.HTTP_201_CREATED)
async def add_handle(
    entity_id: uuid.UUID,
    body: HandleCreate,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    entity = (await session.execute(select(Entity).where(Entity.id == entity_id))).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    handle = Handle(
        entity_id=entity_id,
        handle_type=body.handle_type,
        handle_value=body.handle_value.lower() if body.handle_type == "email" else body.handle_value,
        is_primary=body.is_primary,
    )
    session.add(handle)
    try:
        await session.commit()
        await session.refresh(handle)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handle already exists")

    return HandleOut(
        id=handle.id,
        entity_id=handle.entity_id,
        handle_type=handle.handle_type,
        handle_value=handle.handle_value,
        is_primary=handle.is_primary,
        created_at=handle.created_at,
    )


@router.delete("/{entity_id}/handles/{handle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_handle(
    entity_id: uuid.UUID,
    handle_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    handle = (
        await session.execute(
            select(Handle).where(Handle.id == handle_id, Handle.entity_id == entity_id)
        )
    ).scalar_one_or_none()
    if handle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handle not found")
    await session.delete(handle)
    await session.commit()


# ── Attribute CRUD ───────────────────────────────────────


@router.post("/{entity_id}/attributes", response_model=AttributeOut, status_code=status.HTTP_201_CREATED)
async def add_attribute(
    entity_id: uuid.UUID,
    body: AttributeCreate,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    entity = (await session.execute(select(Entity).where(Entity.id == entity_id))).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    attr = Attribute(
        entity_id=entity_id,
        attr_key=body.attr_key,
        attr_value=body.attr_value,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
    )
    session.add(attr)
    try:
        await session.commit()
        await session.refresh(attr)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate attribute")

    return AttributeOut(
        id=attr.id,
        entity_id=attr.entity_id,
        attr_key=attr.attr_key,
        attr_value=attr.attr_value,
        valid_from=attr.valid_from,
        valid_to=attr.valid_to,
        created_at=attr.created_at,
    )


@router.delete("/{entity_id}/attributes/{attr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_attribute(
    entity_id: uuid.UUID,
    attr_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    attr = (
        await session.execute(
            select(Attribute).where(Attribute.id == attr_id, Attribute.entity_id == entity_id)
        )
    ).scalar_one_or_none()
    if attr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")
    await session.delete(attr)
    await session.commit()


# ── Batch upload ─────────────────────────────────────────


@router.post("/batch", response_model=BatchUploadResult)
async def batch_upload_json(
    items: list[BatchEntityItem],
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    """Batch upload entities from JSON array."""
    return await _process_batch(items, session, current_user["id"])


@router.post("/batch/csv", response_model=BatchUploadResult)
async def batch_upload_csv(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_entity_session)],
    current_user: Annotated[dict, Depends(require_role("admin"))],
):
    """Batch upload entities from CSV file.

    CSV columns: display_name, entity_type, handle_type, handle_value, is_primary
    Additional columns are treated as attributes.
    Rows with the same display_name + entity_type are merged.
    """
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    # Group rows by (display_name, entity_type)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in reader:
        key = (row["display_name"], row["entity_type"])
        groups[key].append(row)

    reserved_cols = {"display_name", "entity_type", "handle_type", "handle_value", "is_primary"}
    items: list[BatchEntityItem] = []

    for (display_name, entity_type), rows in groups.items():
        handles = []
        attrs: dict[str, str] = {}

        for row in rows:
            if row.get("handle_type") and row.get("handle_value"):
                handles.append(
                    HandleCreate(
                        handle_type=row["handle_type"],
                        handle_value=row["handle_value"],
                        is_primary=row.get("is_primary", "").lower() in ("true", "1", "yes"),
                    )
                )
            # Collect non-empty attribute columns
            for col, val in row.items():
                if col not in reserved_cols and val:
                    attrs[col] = val

        items.append(
            BatchEntityItem(
                display_name=display_name,
                entity_type=entity_type,
                handles=handles,
                attributes=[AttributeCreate(attr_key=k, attr_value=v) for k, v in attrs.items()],
            )
        )

    return await _process_batch(items, session, current_user["id"])


async def _process_batch(
    items: list[BatchEntityItem],
    session: AsyncSession,
    created_by: uuid.UUID,
) -> BatchUploadResult:
    created = 0
    updated = 0
    errors: list[str] = []

    for item in items:
        try:
            # Check if entity already exists
            existing = (
                await session.execute(
                    select(Entity)
                    .options(selectinload(Entity.handles), selectinload(Entity.attributes))
                    .where(Entity.display_name == item.display_name, Entity.entity_type == item.entity_type)
                )
            ).scalar_one_or_none()

            if existing:
                # Add new handles
                for h in item.handles:
                    handle = Handle(
                        entity_id=existing.id,
                        handle_type=h.handle_type,
                        handle_value=h.handle_value.lower() if h.handle_type == "email" else h.handle_value,
                        is_primary=h.is_primary,
                    )
                    session.add(handle)
                # Add new attributes
                for a in item.attributes:
                    attr = Attribute(
                        entity_id=existing.id,
                        attr_key=a.attr_key,
                        attr_value=a.attr_value,
                        valid_from=a.valid_from,
                        valid_to=a.valid_to,
                    )
                    session.add(attr)
                updated += 1
            else:
                entity = Entity(
                    display_name=item.display_name,
                    entity_type=item.entity_type,
                    created_by=created_by,
                )
                for h in item.handles:
                    entity.handles.append(
                        Handle(
                            handle_type=h.handle_type,
                            handle_value=h.handle_value.lower() if h.handle_type == "email" else h.handle_value,
                            is_primary=h.is_primary,
                        )
                    )
                for a in item.attributes:
                    entity.attributes.append(
                        Attribute(
                            attr_key=a.attr_key,
                            attr_value=a.attr_value,
                            valid_from=a.valid_from,
                            valid_to=a.valid_to,
                        )
                    )
                session.add(entity)
                created += 1

            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            errors.append(f"{item.display_name}: {exc.orig}")
            logger.warning("batch_entity_error", display_name=item.display_name, error=str(exc.orig))

    if not errors:
        await session.commit()

    return BatchUploadResult(created=created, updated=updated, errors=errors)
