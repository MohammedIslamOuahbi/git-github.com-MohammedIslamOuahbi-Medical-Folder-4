from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SyncMetadataMixin, TimestampMixin


class CampaignWorker(Base, TimestampMixin, SyncMetadataMixin):
    __tablename__ = "campaign_workers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("medical_campaigns.id"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False, index=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)

    campaign = relationship("MedicalCampaign", back_populates="campaign_workers")
    worker = relationship("Worker", back_populates="campaign_workers")
    added_by_user = relationship("User", back_populates="campaign_workers_added")
