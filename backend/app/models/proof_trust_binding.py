from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
class ProofTrustBinding(Base):
    __tablename__ = "proof_trust_bindings"
    __table_args__ = (UniqueConstraint("signing_key_id", "issuer_uuid", "clinic_uuid", "origin_service_uuid", "policy_version", name="uq_proof_trust_binding_identity"),)
    binding_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    signing_key_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    issuer_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revocation_authority_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chain_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    chain_contract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    clinic_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    origin_service_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    binding_version: Mapped[int] = mapped_column(nullable=False, default=1)
    approval_source: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
