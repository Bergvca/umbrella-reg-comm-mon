"""Agent CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from elasticsearch import AsyncElasticsearch

from umbrella_ui.auth.rbac import require_role
from umbrella_ui.db.models.agent import (
    AgentDataSource,
    AgentDefinition,
    AgentModel,
    AgentTool,
    AgentToolLink,
)
from umbrella_ui.deps import get_agent_session, get_es
from umbrella_ui.schemas.agent import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    DataSourceConfig,
    ModelOut,
    ToolSummary,
)
from umbrella_ui.schemas.common import PaginatedResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _agent_to_out(agent: AgentDefinition) -> AgentOut:
    model_ref = agent.model_ref
    return AgentOut(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        model=ModelOut(
            id=model_ref.id,
            name=model_ref.name,
            provider=model_ref.provider,
            model_id=model_ref.model_id,
            base_url=model_ref.base_url,
            max_tokens=model_ref.max_tokens,
            is_active=model_ref.is_active,
            created_by=model_ref.created_by,
            created_at=model_ref.created_at,
            updated_at=model_ref.updated_at,
        ),
        system_prompt=agent.system_prompt,
        temperature=float(agent.temperature),
        max_iterations=agent.max_iterations,
        output_schema=agent.output_schema,
        tools=[
            ToolSummary(
                id=tl.tool.id,
                name=tl.tool.name,
                display_name=tl.tool.display_name,
                tool_config=tl.tool_config,
            )
            for tl in agent.tool_links
        ],
        data_sources=[
            DataSourceConfig(
                source_type=ds.source_type,
                source_identifier=ds.source_identifier,
            )
            for ds in agent.data_sources
        ],
        is_builtin=agent.is_builtin,
        is_active=agent.is_active,
        created_by=agent.created_by,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


_AGENT_LOAD_OPTIONS = [
    selectinload(AgentDefinition.model_ref),
    selectinload(AgentDefinition.tool_links).selectinload(AgentToolLink.tool),
    selectinload(AgentDefinition.data_sources),
]


@router.get("", response_model=PaginatedResponse[AgentOut])
async def list_agents(
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
    is_builtin: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    base = select(AgentDefinition)
    if is_builtin is not None:
        base = base.where(AgentDefinition.is_builtin == is_builtin)
    if is_active is not None:
        base = base.where(AgentDefinition.is_active == is_active)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.options(*_AGENT_LOAD_OPTIONS).offset(offset).limit(limit).order_by(AgentDefinition.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[_agent_to_out(a) for a in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("reviewer"))],
):
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id).options(*_AGENT_LOAD_OPTIONS)
    agent = (await session.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _agent_to_out(agent)


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    current_user: Annotated[dict, Depends(require_role("supervisor"))],
):
    agent = AgentDefinition(
        name=body.name,
        description=body.description,
        model_id=body.model_id,
        system_prompt=body.system_prompt,
        temperature=body.temperature,
        max_iterations=body.max_iterations,
        output_schema=body.output_schema,
        created_by=current_user["id"],
    )

    # Add tool links
    for tool_id in body.tool_ids:
        config = (body.tool_configs or {}).get(str(tool_id))
        agent.tool_links.append(AgentToolLink(tool_id=tool_id, tool_config=config))

    # Add data sources
    for ds in body.data_sources:
        agent.data_sources.append(AgentDataSource(
            source_type=ds.source_type,
            source_identifier=ds.source_identifier,
        ))

    session.add(agent)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent with this name already exists for this user",
        )

    # Re-query with eager loads so nested relationships (tool_links→tool) are available.
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent.id).options(*_AGENT_LOAD_OPTIONS)
    agent = (await session.execute(stmt)).scalar_one()
    return _agent_to_out(agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id).options(*_AGENT_LOAD_OPTIONS)
    agent = (await session.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.description is not None:
        agent.description = body.description
    if body.model_id is not None:
        agent.model_id = body.model_id
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.temperature is not None:
        agent.temperature = body.temperature
    if body.max_iterations is not None:
        agent.max_iterations = body.max_iterations
    if body.output_schema is not None:
        agent.output_schema = body.output_schema
    if body.is_active is not None:
        agent.is_active = body.is_active

    # Replace tool links if provided
    if body.tool_ids is not None:
        for tl in list(agent.tool_links):
            await session.delete(tl)
        await session.flush()
        for tool_id in body.tool_ids:
            config = (body.tool_configs or {}).get(str(tool_id))
            session.add(AgentToolLink(agent_id=agent_id, tool_id=tool_id, tool_config=config))

    # Replace data sources if provided
    if body.data_sources is not None:
        for ds in list(agent.data_sources):
            await session.delete(ds)
        await session.flush()
        for ds in body.data_sources:
            session.add(AgentDataSource(
                agent_id=agent_id,
                source_type=ds.source_type,
                source_identifier=ds.source_identifier,
            ))

    agent.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate agent name")

    # Re-query with eager loads so nested relationships (tool_links→tool) are available.
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id).options(*_AGENT_LOAD_OPTIONS)
    agent = (await session.execute(stmt)).scalar_one()
    return _agent_to_out(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_agent_session)],
    _user: Annotated[dict, Depends(require_role("admin"))],
):
    """Soft-delete: set is_active=false."""
    agent = (await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent.is_active = False
    agent.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    await session.commit()


# ── Data-source discovery ──────────────────────────────────────────

ds_router = APIRouter(prefix="/api/v1/agent-data-sources", tags=["agents"])

# Only data-oriented schemas/tables; excludes iam, agent, policy internals.
_SAFE_PG_TABLES: list[str] = [
    "alert.alerts",
    "alert.generation_jobs",
    "entity.entities",
    "entity.handles",
    "entity.attributes",
    "review.queues",
    "review.queue_batches",
    "review.queue_items",
    "review.decisions",
    "review.decision_statuses",
    "review.audit_log",
]

_WELL_KNOWN_ES_ALIASES: list[str] = ["messages", "alerts"]


@ds_router.get("/options")
async def get_data_source_options(
    es: Annotated[AsyncElasticsearch, Depends(get_es)],
    _user: Annotated[dict, Depends(require_role("supervisor"))],
):
    """Return available ES indices and safe PG tables for agent data sources."""
    indices: list[str] = []
    try:
        cat_result = await es.cat.indices(format="json")
        indices = sorted(
            {
                idx["index"]
                for idx in cat_result
                if not idx["index"].startswith(".")
            }
        )
    except Exception:
        logger.warning("failed to list ES indices for data-source options")

    # Merge well-known aliases (deduplicated, aliases first)
    all_es = list(dict.fromkeys(_WELL_KNOWN_ES_ALIASES + indices))

    return {
        "elasticsearch_indices": all_es,
        "postgresql_tables": _SAFE_PG_TABLES,
    }
