from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, TimestampMixin


class Prescription(Base, TimestampMixin, SoftDeleteMixin, SyncMetadataMixin):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("medical_campaigns.id"), nullable=False, index=True)
    medical_visit_id: Mapped[int | None] = mapped_column(ForeignKey("medical_visits.id"), nullable=True, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    prescription_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    prescription_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    include_validator_signature: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validator_id: Mapped[int | None] = mapped_column(nullable=True)
    validator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validator_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validator_signature_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)

    worker = relationship("Worker", back_populates="prescriptions")
    campaign = relationship("MedicalCampaign", back_populates="prescriptions")
    medical_visit = relationship("MedicalVisit", back_populates="prescriptions")
    doctor = relationship("User", back_populates="prescriptions_signed")
    items = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.id",
    )
