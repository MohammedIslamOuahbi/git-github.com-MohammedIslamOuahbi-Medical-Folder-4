from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SyncMetadataMixin, SyncMixin, TimestampMixin


class Workspace(Base, TimestampMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("medical_campaigns.id"), unique=True, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    drilling_site_id: Mapped[int | None] = mapped_column(ForeignKey("drilling_sites.id"), index=True)
    workspace_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    workspace_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(JSON)

    campaign = relationship("MedicalCampaign", back_populates="workspace")
    company = relationship("Company")
    branch = relationship("Branch")
    drilling_site = relationship("DrillingSite")
