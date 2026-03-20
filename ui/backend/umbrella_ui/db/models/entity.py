"""SQLAlchemy ORM models for the entity schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .iam import Base


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = {"schema": "entity"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )

    handles: Mapped[list[Handle]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    attributes: Mapped[list[Attribute]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )


class Handle(Base):
    __tablename__ = "handles"
    __table_args__ = {"schema": "entity"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity.entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    handle_type: Mapped[str] = mapped_column(Text, nullable=False)
    handle_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    entity: Mapped[Entity] = relationship(back_populates="handles")


class Attribute(Base):
    __tablename__ = "attributes"
    __table_args__ = {"schema": "entity"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity.entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    attr_key: Mapped[str] = mapped_column(Text, nullable=False)
    attr_value: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column()
    valid_to: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    entity: Mapped[Entity] = relationship(back_populates="attributes")
