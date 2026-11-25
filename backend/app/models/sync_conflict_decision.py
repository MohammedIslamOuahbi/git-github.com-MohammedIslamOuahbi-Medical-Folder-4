from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SyncConflictDecision(Base):
    __tablename__ = "sync_conflict_decisions"

    decision_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operation_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    conflict_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    incoming_event_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    incoming_revision_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    local_parent_revision_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision_revision_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    local_version: Mapped[int] = mapped_column(Integer, nullable=False)
    incoming_version: Mapped[int] = mapped_column(Integer, nullable=False)
    local_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    incoming_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    local_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    incoming_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_user_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trust_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
