from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SyncMetadataMixin, TimestampMixin


class AssistantCampaign(Base, TimestampMixin, SyncMetadataMixin):
    __tablename__ = "assistant_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    assistant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("medical_campaigns.id"), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    assistant = relationship("User", back_populates="assistant_assignments")
    campaign = relationship("MedicalCampaign", back_populates="assistant_assignments")
