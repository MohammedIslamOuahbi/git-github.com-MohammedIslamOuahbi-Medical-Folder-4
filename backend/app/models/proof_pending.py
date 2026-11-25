from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class AuthorizationPolicy(Base):
    __tablename__ = "authorization_policies"
    policy_version: Mapped[str] = mapped_column(String(40), primary_key=True)
    offline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    time_reference: Mapped[str] = mapped_column(String(40), nullable=False)
    unknown_time_action: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class OriginProofRequest(Base):
    __tablename__ = "origin_proof_requests"
    request_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operation_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    event_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_revision_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    origin_user_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    origin_device_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    clinic_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    proof_transport_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reason_code: Mapped[str | None] = mapped_column(String(100))
    time_state: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

def proof_request_binding_valid(request: OriginProofRequest, *, event_uuid, content_sha256,
                                operation_uuid, entity_type, revision_uuid) -> bool:
    """P1 binding check; signature/trust validation remains P2."""
    return (request.event_uuid == event_uuid and request.content_sha256 == content_sha256
            and request.operation_uuid == operation_uuid and request.entity_type == entity_type
            and request.revision_uuid == revision_uuid)
