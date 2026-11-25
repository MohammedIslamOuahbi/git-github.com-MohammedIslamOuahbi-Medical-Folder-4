from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, SyncMixin, TimestampMixin


class MedicalCampaign(Base, TimestampMixin, SoftDeleteMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "medical_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    drilling_site_id: Mapped[int | None] = mapped_column(ForeignKey("drilling_sites.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    company = relationship("Company", back_populates="campaigns")
    branch = relationship("Branch", back_populates="campaigns")
    drilling_site = relationship("DrillingSite", back_populates="campaigns")
    creator = relationship("User", back_populates="created_campaigns")
    campaign_workers = relationship("CampaignWorker", back_populates="campaign", cascade="all, delete-orphan")
    campaign_tests = relationship("CampaignTest", back_populates="campaign", cascade="all, delete-orphan")
    worker_tests = relationship("WorkerTest", back_populates="campaign")
    doctor_assignments = relationship("DoctorCampaign", back_populates="campaign", cascade="all, delete-orphan")
    assistant_assignments = relationship("AssistantCampaign", back_populates="campaign", cascade="all, delete-orphan")
    import_jobs = relationship("ImportJob", back_populates="campaign")
    workspace = relationship("Workspace", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="campaign")
    orientation_certificates = relationship("OrientationCertificate", back_populates="campaign", cascade="all, delete-orphan")
    aptitude_certificates = relationship("AptitudeCertificate", back_populates="campaign", cascade="all, delete-orphan")
