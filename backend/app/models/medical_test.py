from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SyncMetadataMixin, SyncMixin, TimestampMixin


class MedicalTest(Base, TimestampMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "medical_tests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    normal_range: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_doctor_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    campaign_tests = relationship("CampaignTest", back_populates="test")
    worker_tests = relationship("WorkerTest", back_populates="test")

    @property
    def active(self) -> bool:
        return bool(self.is_active)

    @active.setter
    def active(self, value: bool) -> None:
        self.is_active = bool(value)
