"""SQLAlchemy ORM models for the alert schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from umbrella_ui.db.models.iam import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"schema": "alert"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy.rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    es_index: Mapped[str] = mapped_column(Text, nullable=False)
    es_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    es_document_ts: Mapped[datetime | None] = mapped_column()
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = {"schema": "alert"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    query_kql: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_kql_resolved: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    alerts_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rules_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    documents_scanned: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    schedule_cron: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
