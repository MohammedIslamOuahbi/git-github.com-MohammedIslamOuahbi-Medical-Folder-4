from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime,JSON,String,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
class RevocationCheckpoint(Base):
 __tablename__='proof_revocation_checkpoints'
 __table_args__=(UniqueConstraint('authority_uuid','chain_scope','covered_sequence',name='uq_revocation_checkpoint_sequence'),)
 checkpoint_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True)
 authority_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
 authority_key_id:Mapped[str]=mapped_column(String(120),nullable=False)
 chain_scope:Mapped[str]=mapped_column(String(160),nullable=False)
 contract_version:Mapped[str]=mapped_column(String(40),nullable=False)
 policy_version:Mapped[str]=mapped_column(String(40),nullable=False)
 covered_sequence:Mapped[int]=mapped_column(nullable=False)
 covered_chain_hash:Mapped[str]=mapped_column(String(64),nullable=False)
 challenge:Mapped[str]=mapped_column(String(120),nullable=False)
 destination_device_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
 canonicalization_version:Mapped[str]=mapped_column(String(80),nullable=False)
 signature:Mapped[str]=mapped_column(String,nullable=False)
 is_current:Mapped[bool]=mapped_column(nullable=False,default=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
