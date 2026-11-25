from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, JSON, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
class ProofTrustedKey(Base):
 __tablename__="proof_trusted_keys"; key_id:Mapped[str]=mapped_column(String(120),primary_key=True); clinic_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); origin_service_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); registration_authority_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); public_key:Mapped[str]=mapped_column(Text()); algorithm:Mapped[str]=mapped_column(String(30)); canonicalization_version:Mapped[str]=mapped_column(String(30)); state:Mapped[str]=mapped_column(String(20)); registered_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); retired_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class ProofDelegation(Base):
 __tablename__="proof_delegations"; delegation_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True); clinic_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); origin_service_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); user_uuid:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True)); entity_type:Mapped[str]=mapped_column(String(100)); operation:Mapped[str]=mapped_column(String(20)); policy_version:Mapped[str]=mapped_column(String(40)); issued_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); state:Mapped[str]=mapped_column(String(20)); authority_ref:Mapped[str]=mapped_column(String(160))
class ProofRevocation(Base):
 __tablename__="proof_revocations"; revocation_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True); target_type:Mapped[str]=mapped_column(String(30)); target_ref:Mapped[str]=mapped_column(String(160)); reason_code:Mapped[str]=mapped_column(String(100)); effective_at_declared:Mapped[datetime]=mapped_column(DateTime(timezone=True)); authority_ref:Mapped[str]=mapped_column(String(160)); recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ProofVerificationResult(Base):
 __tablename__="proof_verification_results"; verification_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True); event_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); content_sha256:Mapped[str]=mapped_column(String(64)); proof_format_version:Mapped[str]=mapped_column(String(30)); signature_result:Mapped[str]=mapped_column(String(30)); binding_result:Mapped[str]=mapped_column(String(30)); key_trust_result:Mapped[str]=mapped_column(String(30)); delegation_result:Mapped[str]=mapped_column(String(30)); time_result:Mapped[str]=mapped_column(String(30)); decision:Mapped[str]=mapped_column(String(40)); evidence_refs:Mapped[dict]=mapped_column(JSON); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
