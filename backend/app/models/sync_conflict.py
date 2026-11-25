from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SyncConflict(Base, TimestampMixin):
    __tablename__ = "sync_conflicts"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_sync_conflicts_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True, default=py_uuid.uuid4)
    mission_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    incoming_change_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    source_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    source_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    mission_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    base_version: Mapped[int | None] = mapped_column(nullable=True)
    central_version: Mapped[int | None] = mapped_column(nullable=True)
    conflicting_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    central_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mission_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    resolution_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolved_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_by_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
