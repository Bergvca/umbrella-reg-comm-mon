"""SQLAlchemy ORM models for the alert schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
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
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
