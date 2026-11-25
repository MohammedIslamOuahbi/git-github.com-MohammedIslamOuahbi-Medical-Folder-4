import uuid
from datetime import datetime
from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
class AuthorizationEvidenceRecord(Base):
    __tablename__ = "authorization_evidence_records"
    __table_args__ = (UniqueConstraint("evidence_uuid", name="uq_authorization_evidence_uuid"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issuer_key_id: Mapped[str | None] = mapped_column(String(120))
    contract_version: Mapped[str | None] = mapped_column(String(40))
    trust_reference: Mapped[str | None] = mapped_column(String(200))
    event_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_user_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    clinic_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(200), nullable=False)
    envelope: Mapped[dict] = mapped_column(JSON, nullable=False)
    envelope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
