import uuid
from datetime import datetime
from sqlalchemy import DateTime,Integer,String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
class ProofTransportCapability(Base):
 __tablename__='proof_transport_capabilities'; peer_device_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True); connection_scope:Mapped[str]=mapped_column(String(160),primary_key=True); proof_transport_version:Mapped[int]=mapped_column(Integer); advertisement_uuid:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True)); advertisement_sequence:Mapped[int]=mapped_column(Integer, nullable=False, default=0); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
