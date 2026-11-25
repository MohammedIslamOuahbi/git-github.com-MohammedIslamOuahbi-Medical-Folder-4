from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, SyncMixin, TimestampMixin


class Medicine(Base, TimestampMixin, SoftDeleteMixin, SyncMixin):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registration_number: Mapped[str | None] = mapped_column(String(255), index=True)
    national_code: Mapped[str | None] = mapped_column(String(255), index=True)
    stable_identity_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    international_nonproprietary_name: Mapped[str | None] = mapped_column(String(500), index=True)
    brand_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(600))

    pharmaceutical_form: Mapped[str | None] = mapped_column(String(500))
    source_pharmaceutical_form: Mapped[str | None] = mapped_column(String(500))
    strength: Mapped[str | None] = mapped_column(String(500))
    packaging: Mapped[str | None] = mapped_column(String(500))

    list_category: Mapped[str | None] = mapped_column(String(100))
    p1: Mapped[str | None] = mapped_column(String(255))
    p2: Mapped[str | None] = mapped_column(String(255))
    observations: Mapped[str | None] = mapped_column(Text)

    laboratory: Mapped[str | None] = mapped_column(String(500), index=True)
    registration_holder: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(255))
    medicine_type: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_prescribable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(255))
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    source_import_id: Mapped[int | None] = mapped_column(ForeignKey("medicine_imports.id"), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    normalized_brand_name: Mapped[str | None] = mapped_column(String(500), index=True)
    normalized_generic_name: Mapped[str | None] = mapped_column(String(500), index=True)
    search_text: Mapped[str | None] = mapped_column(Text)

    source_import = relationship("MedicineImport", back_populates="medicines")


Index("ix_medicines_brand_name_lower", Medicine.normalized_brand_name)
Index("ix_medicines_generic_name_lower", Medicine.normalized_generic_name)
