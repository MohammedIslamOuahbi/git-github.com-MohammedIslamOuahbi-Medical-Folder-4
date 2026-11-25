from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class DeviceSyncState(Base, TimestampMixin):
    __tablename__ = "device_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    remote_server_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, index=True)
    remote_server_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    remote_server_url: Mapped[str] = mapped_column(Text, nullable=False)
    mission_session_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    last_pulled_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_pushed_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    final_mission_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    copy_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started")
    copy_started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    copy_completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_push_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pull_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    is_sync_running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_run_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
