from __future__ import annotations

import uuid as py_uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, TimestampMixin


class MedicalVisit(Base, TimestampMixin, SoftDeleteMixin, SyncMetadataMixin):
    __tablename__ = "medical_visits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), unique=True, index=True, nullable=False, default=py_uuid.uuid4)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"), index=True, nullable=True)
    worker_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), index=True, nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("medical_campaigns.id"), index=True, nullable=True)
    campaign_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), index=True, nullable=True)
    visit_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)
    form_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), default="pending_sync", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}

    worker = relationship("Worker")
    campaign = relationship("MedicalCampaign")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    validator = relationship("User", foreign_keys=[validated_by])
    orientation_certificates = relationship("OrientationCertificate", back_populates="medical_visit")
    aptitude_certificates = relationship("AptitudeCertificate", back_populates="medical_visit")
    prescriptions = relationship("Prescription", back_populates="medical_visit")
