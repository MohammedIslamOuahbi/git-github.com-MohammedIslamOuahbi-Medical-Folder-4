from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SyncDevice(Base, TimestampMixin):
    __tablename__ = "sync_devices"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_sync_devices_uuid"),
        UniqueConstraint("installation_uuid", name="uq_sync_devices_installation_uuid"),
        UniqueConstraint("device_code", name="uq_sync_devices_device_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
    )
    installation_uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=py_uuid.uuid4,
    )
    device_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_category: Mapped[str] = mapped_column(String(50), nullable=False, default="desktop")
    connection_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_central_server: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_local_activity_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_mission_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_central_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schema_revision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    central_secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
