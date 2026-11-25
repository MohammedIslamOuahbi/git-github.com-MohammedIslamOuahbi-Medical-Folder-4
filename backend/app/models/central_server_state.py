from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class CentralServerState(Base, TimestampMixin):
    __tablename__ = "central_server_state"
    __table_args__ = (
        UniqueConstraint("server_uuid", name="uq_central_server_state_server_uuid"),
        UniqueConstraint("server_generation_uuid", name="uq_central_server_state_generation_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    server_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True)
    server_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True)
    device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("sync_devices.uuid"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="inactive", index=True)
    schema_revision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    current_central_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    activated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
