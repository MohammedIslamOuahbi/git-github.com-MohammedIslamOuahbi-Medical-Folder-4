from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SyncChange(Base, TimestampMixin):
    __tablename__ = "sync_changes"
    __table_args__ = (
        UniqueConstraint("change_uuid", name="uq_sync_changes_change_uuid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
    )
    revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, unique=True)
    operation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    schema_version: Mapped[int | None] = mapped_column(nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    source_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    source_clinic_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    base_version: Mapped[int | None] = mapped_column(nullable=True)
    parent_revision_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    entity_version: Mapped[int] = mapped_column(nullable=False)
    changed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    source_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    mission_session_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    mission_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    mission_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    central_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    central_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    central_status: Mapped[str] = mapped_column(String(30), nullable=False, default="never_submitted", index=True)
    occurred_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    mission_committed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    copied_to_client_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to_central_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    central_accepted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    central_finalized_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
