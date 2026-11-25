from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime,String,UniqueConstraint,JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
class RevocationChainRecord(Base):
 __tablename__='proof_revocation_chain_records'
 __table_args__=(UniqueConstraint('authority_uuid','chain_scope','sequence',name='uq_revocation_chain_sequence'),)
 record_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True)
 authority_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False)
 chain_scope:Mapped[str]=mapped_column(String(160),nullable=False)
 contract_version:Mapped[str]=mapped_column(String(40),nullable=False)
 canonicalization_version:Mapped[str]=mapped_column(String(80),nullable=False)
 sequence:Mapped[int]=mapped_column(nullable=False)
 previous_record_hash:Mapped[str]=mapped_column(String(64),nullable=False)
 record_hash:Mapped[str]=mapped_column(String(64),nullable=False)
 record:Mapped[dict]=mapped_column(JSON,nullable=False)
 signature:Mapped[str]=mapped_column(String,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
