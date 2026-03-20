"""SQLAlchemy 2.0 models for the ``agent`` schema (UI backend CRUD)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AgentBase(DeclarativeBase):
    pass


class AgentModel(AgentBase):
    """``agent.models`` — registered LLM endpoints."""

    __tablename__ = "models"
    __table_args__ = {"schema": "agent"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    api_key_secret: Mapped[str | None] = mapped_column(Text)
    max_tokens: Mapped[int] = mapped_column(default=4096)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class AgentTool(AgentBase):
    """``agent.tools`` — tool registry."""

    __tablename__ = "tools"
    __table_args__ = {"schema": "agent"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class AgentDefinition(AgentBase):
    """``agent.agents`` — agent definitions."""

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("name", "created_by"),
        {"schema": "agent"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.models.id"), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[Decimal] = mapped_column(default=Decimal("0.00"))
    max_iterations: Mapped[int] = mapped_column(default=10)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    is_builtin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")

    model_ref: Mapped[AgentModel] = relationship(lazy="selectin", foreign_keys=[model_id])
    tool_links: Mapped[list[AgentToolLink]] = relationship(back_populates="agent", lazy="selectin")
    data_sources: Mapped[list[AgentDataSource]] = relationship(back_populates="agent", lazy="selectin")


class AgentToolLink(AgentBase):
    """``agent.agent_tools`` — many-to-many agent ↔ tools."""

    __tablename__ = "agent_tools"
    __table_args__ = {"schema": "agent"}

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.agents.id", ondelete="CASCADE"), primary_key=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.tools.id", ondelete="CASCADE"), primary_key=True)
    tool_config: Mapped[dict | None] = mapped_column(JSONB)

    agent: Mapped[AgentDefinition] = relationship(back_populates="tool_links")
    tool: Mapped[AgentTool] = relationship(lazy="selectin")


class AgentDataSource(AgentBase):
    """``agent.agent_data_sources`` — per-agent data access control."""

    __tablename__ = "agent_data_sources"
    __table_args__ = (
        UniqueConstraint("agent_id", "source_type", "source_identifier"),
        {"schema": "agent"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.agents.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    access_mode: Mapped[str] = mapped_column(Text, default="read")

    agent: Mapped[AgentDefinition] = relationship(back_populates="data_sources")


class AgentRun(AgentBase):
    """``agent.runs`` — execution log."""

    __tablename__ = "runs"
    __table_args__ = {"schema": "agent"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    iterations: Mapped[int | None]
    duration_ms: Mapped[int | None]
    triggered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    completed_at: Mapped[datetime | None]

    steps: Mapped[list[AgentRunStep]] = relationship(back_populates="run", lazy="selectin", order_by="AgentRunStep.step_order")


class AgentRunStep(AgentBase):
    """``agent.run_steps`` — step trace within a run."""

    __tablename__ = "run_steps"
    __table_args__ = {"schema": "agent"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.runs.id", ondelete="CASCADE"), nullable=False)
    step_order: Mapped[int] = mapped_column(nullable=False)
    step_type: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    run: Mapped[AgentRun] = relationship(back_populates="steps")
