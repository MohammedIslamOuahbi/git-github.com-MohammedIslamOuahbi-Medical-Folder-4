from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, SyncMixin, TimestampMixin


class User(Base, TimestampMixin, SoftDeleteMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    qualification: Mapped[str | None] = mapped_column(String(255))
    signature_png: Mapped[str | None] = mapped_column(Text)
    signature_path: Mapped[str | None] = mapped_column(String(500))
    signature_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signature_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signature_image_path = synonym("signature_path")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permissions_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_permissions_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_campaigns = relationship("MedicalCampaign", back_populates="creator")
    doctor_assignments = relationship("DoctorCampaign", back_populates="doctor", foreign_keys="DoctorCampaign.doctor_id")
    assistant_assignments = relationship(
        "AssistantCampaign", back_populates="assistant", foreign_keys="AssistantCampaign.assistant_id"
    )
    worker_tests = relationship("WorkerTest", back_populates="doctor", foreign_keys="WorkerTest.doctor_id")
    audit_logs = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.user_id")
    uploaded_import_jobs = relationship("ImportJob", back_populates="uploaded_by_user")
    medicine_imports_started = relationship("MedicineImport", back_populates="started_by_user")
    campaign_workers_added = relationship("CampaignWorker", back_populates="added_by_user")
    user_permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserPermission.user_id")
    granted_user_permissions = relationship(
        "UserPermission", back_populates="granted_by", foreign_keys="UserPermission.granted_by_user_id"
    )
    prescriptions_signed = relationship("Prescription", back_populates="doctor")
    orientation_certificates_signed = relationship("OrientationCertificate", back_populates="doctor")
    aptitude_certificates_signed = relationship("AptitudeCertificate", back_populates="doctor")
    assigned_role = relationship("Role", back_populates="users")
