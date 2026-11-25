from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMetadataMixin, SyncMixin, TimestampMixin


class Company(Base, TimestampMixin, SoftDeleteMixin, SyncMixin, SyncMetadataMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    contract_start_date: Mapped[date | None] = mapped_column(Date)
    contract_end_date: Mapped[date | None] = mapped_column(Date)
    contact_person: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    branches = relationship("Branch", back_populates="company")
    drilling_sites = relationship("DrillingSite", back_populates="company")
    workers = relationship("Worker", back_populates="company")
    campaigns = relationship("MedicalCampaign", back_populates="company")
    import_jobs = relationship("ImportJob", back_populates="company")
