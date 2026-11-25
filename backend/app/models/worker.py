from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, SyncMixin, TimestampMixin


class Worker(Base, TimestampMixin, SoftDeleteMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("national_id", name="uq_workers_national_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    drilling_site_id: Mapped[int | None] = mapped_column(ForeignKey("drilling_sites.id"), index=True)
    employee_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    national_id: Mapped[str | None] = mapped_column(String(100), index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20))
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_wilaya: Mapped[str | None] = mapped_column(String(100))
    marital_status: Mapped[str | None] = mapped_column(String(50))
    blood_group: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(50))
    emergency_phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    hire_date: Mapped[date | None] = mapped_column(Date)
    medical_status: Mapped[str | None] = mapped_column(String(100))
    etat_actual: Mapped[str] = mapped_column(String(50), nullable=False, default="present")
    medical_file_data: Mapped[dict | None] = mapped_column(JSON)
    photo: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company = relationship("Company", back_populates="workers")
    branch = relationship("Branch", back_populates="workers")
    drilling_site = relationship("DrillingSite", back_populates="workers")
    campaign_workers = relationship("CampaignWorker", back_populates="worker")
    worker_tests = relationship("WorkerTest", back_populates="worker")
    import_rows = relationship("ImportRow", back_populates="matched_worker")
    prescriptions = relationship("Prescription", back_populates="worker")
    orientation_certificates = relationship("OrientationCertificate", back_populates="worker" )
    aptitude_certificates = relationship("AptitudeCertificate", back_populates="worker")
