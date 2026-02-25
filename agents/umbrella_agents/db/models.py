"""SQLAlchemy 2.0 models for the ``agent`` schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Model(Base):
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


class Tool(Base):
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


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("name", "created_by"),
        Index("ix_agent_agents_model_id", "model_id"),
        Index("ix_agent_agents_created_by", "created_by"),
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

    model: Mapped[Model] = relationship(lazy="selectin")
    tools: Mapped[list[AgentTool]] = relationship(back_populates="agent", lazy="selectin")
    data_sources: Mapped[list[AgentDataSource]] = relationship(back_populates="agent", lazy="selectin")


class AgentTool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (
        Index("ix_agent_agent_tools_tool_id", "tool_id"),
        {"schema": "agent"},
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.agents.id", ondelete="CASCADE"), primary_key=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.tools.id", ondelete="CASCADE"), primary_key=True)
    tool_config: Mapped[dict | None] = mapped_column(JSONB)

    agent: Mapped[Agent] = relationship(back_populates="tools")
    tool: Mapped[Tool] = relationship(lazy="selectin")


class AgentDataSource(Base):
    __tablename__ = "agent_data_sources"
    __table_args__ = (
        UniqueConstraint("agent_id", "source_type", "source_identifier"),
        Index("ix_agent_agent_data_sources_agent_id", "agent_id"),
        {"schema": "agent"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent.agents.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    access_mode: Mapped[str] = mapped_column(Text, default="read")

    agent: Mapped[Agent] = relationship(back_populates="data_sources")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_agent_runs_agent_id", "agent_id"),
        Index("ix_agent_runs_triggered_by", "triggered_by"),
        Index("ix_agent_runs_created_at", "created_at"),
        Index("ix_agent_runs_status", "status"),
        {"schema": "agent"},
    )

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

    steps: Mapped[list[RunStep]] = relationship(back_populates="run", lazy="selectin", order_by="RunStep.step_order")


class RunStep(Base):
    __tablename__ = "run_steps"
    __table_args__ = (
        Index("ix_agent_run_steps_run_id_step_order", "run_id", "step_order"),
        {"schema": "agent"},
    )

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

    run: Mapped[Run] = relationship(back_populates="steps")
