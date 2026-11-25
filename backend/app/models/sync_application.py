from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class SyncApplicationDecision(Base):
    __tablename__ = "sync_application_decisions"
    __table_args__ = (UniqueConstraint("event_uuid", name="uq_sync_application_decision_event"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SyncApplicationAttempt(Base):
    __tablename__ = "sync_application_attempts"
    __table_args__ = (UniqueConstraint("event_uuid", "input_fingerprint", name="uq_sync_application_attempt_input"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
