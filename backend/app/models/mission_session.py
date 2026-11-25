from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class MissionSession(Base, TimestampMixin):
    __tablename__ = "mission_sessions"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_mission_sessions_uuid"),
        UniqueConstraint("mission_code", name="uq_mission_sessions_mission_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
    )
    mission_code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    mission_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_device_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), ForeignKey("sync_devices.uuid"), nullable=False)
    server_device_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="preparing", index=True)
    base_central_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    base_central_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    base_central_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mission_current_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalization_started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    centralization_started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    centralized_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aborted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abort_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
