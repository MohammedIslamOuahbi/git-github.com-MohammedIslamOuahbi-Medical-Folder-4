from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, LocalRuntimeConfigMixin


class RuntimeConfig(Base, LocalRuntimeConfigMixin):
    __tablename__ = "runtime_configs"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    runtime_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="standalone")
    connection_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    connection_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connection_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connection_requires_setup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    connection_server_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_api_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_api_url: Mapped[str] = mapped_column(Text, nullable=False)
    mission_server_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_server_device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    active_mission_session_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    local_database_write_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_mode_change_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_mode_change_by_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
