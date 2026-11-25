from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_sync_runs_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True, default=py_uuid.uuid4)
    direction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    mission_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    remote_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    remote_server_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    cursor_start: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cursor_end: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    accepted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(nullable=False, default=0)
    auto_merged_count: Mapped[int] = mapped_column(nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
