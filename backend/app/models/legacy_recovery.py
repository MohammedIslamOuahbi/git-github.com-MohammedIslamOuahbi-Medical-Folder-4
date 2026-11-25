from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecoverySource(Base):
    __tablename__ = "recovery_sources"
    __table_args__ = (
        UniqueConstraint("source_scope", "source_kind", "logical_key", "sha256", name="uq_recovery_source_snapshot"),
    )

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_scope: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_identity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    byte_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_source_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_sources.uuid"), nullable=True)
    captured_by_user_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="captured")
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    materialized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items: Mapped[list[RecoveryItem]] = relationship(back_populates="source", cascade="all, delete-orphan")


class RecoveryItem(Base):
    __tablename__ = "recovery_items"
    __table_args__ = (UniqueConstraint("source_uuid", "ordinal", name="uq_recovery_item_position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_sources.uuid"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legacy_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[RecoverySource] = relationship(back_populates="items")


class RecoveryIdentityCandidate(Base):
    __tablename__ = "recovery_identity_candidates"
    __table_args__ = (UniqueConstraint("item_id", name="uq_recovery_identity_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recovery_items.id"), nullable=False)
    source_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    legacy_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence: Mapped[str] = mapped_column(String(50), nullable=False, default="source_row_uuid")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate_needs_review")
