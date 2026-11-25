from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
class OriginProofDelivery(Base):
 __tablename__='origin_proof_deliveries'
 __table_args__=(UniqueConstraint('proof_uuid','peer_device_uuid','channel',name='uq_origin_proof_delivery_scope'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 proof_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False,index=True)
 peer_device_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False,index=True)
 channel:Mapped[str]=mapped_column(String(40),nullable=False)
 status:Mapped[str]=mapped_column(String(30),nullable=False,default='pending')
 attempt_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 lease_token:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True))
 lease_expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 delivered_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 last_error_code:Mapped[str|None]=mapped_column(String(100))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
