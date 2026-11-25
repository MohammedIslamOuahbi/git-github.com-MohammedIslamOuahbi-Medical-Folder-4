from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("medical_campaigns.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    mapping_json: Mapped[dict | None] = mapped_column(JSON)
    errors_json: Mapped[dict | None] = mapped_column(JSON)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company = relationship("Company", back_populates="import_jobs")
    campaign = relationship("MedicalCampaign", back_populates="import_jobs")
    uploaded_by_user = relationship("User", back_populates="uploaded_import_jobs")
    rows = relationship("ImportRow", back_populates="import_job", cascade="all, delete-orphan")
