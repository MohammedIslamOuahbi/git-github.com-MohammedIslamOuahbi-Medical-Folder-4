from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, SyncMixin, TimestampMixin


class WorkerTest(Base, TimestampMixin, SoftDeleteMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "worker_tests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("medical_campaigns.id"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False, index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("medical_tests.id"), nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    result: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_normal: Mapped[bool | None] = mapped_column(Boolean)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign = relationship("MedicalCampaign", back_populates="worker_tests")
    worker = relationship("Worker", back_populates="worker_tests")
    test = relationship("MedicalTest", back_populates="worker_tests")
    doctor = relationship("User", back_populates="worker_tests")
