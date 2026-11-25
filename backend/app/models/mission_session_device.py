from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class MissionSessionDevice(Base, TimestampMixin):
    __tablename__ = "mission_session_devices"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_mission_session_devices_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
    )
    mission_session_uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("mission_sessions.uuid"),
        nullable=False,
        index=True,
    )
    device_uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("sync_devices.uuid"),
        nullable=False,
        index=True,
    )
    device_code_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    device_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    joined_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pulled_mission_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_successful_pull_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    local_copy_completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_connected: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="invited", index=True)
