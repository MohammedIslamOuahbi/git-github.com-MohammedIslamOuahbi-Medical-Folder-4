from __future__ import annotations

import uuid as py_uuid

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class CentralBootstrap(Base, TimestampMixin):
    __tablename__ = "central_bootstraps"
    __table_args__ = (
        UniqueConstraint("bootstrap_uuid", name="uq_central_bootstraps_uuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bootstrap_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False, unique=True, default=py_uuid.uuid4)
    device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    central_server_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    central_generation_uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    snapshot_central_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    schema_revision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="requested", index=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_locally: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
