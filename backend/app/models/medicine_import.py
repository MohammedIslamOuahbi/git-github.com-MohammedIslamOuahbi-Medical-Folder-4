from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class MedicineImport(Base, TimestampMixin):
    __tablename__ = "medicine_imports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(255))
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="preview")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded")

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deactivated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mapping_json: Mapped[dict | None] = mapped_column(JSON)
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    started_by_user = relationship("User", back_populates="medicine_imports_started")
    errors = relationship("MedicineImportError", back_populates="medicine_import", cascade="all, delete-orphan")
    medicines = relationship("Medicine", back_populates="source_import")


class MedicineImportError(Base, TimestampMixin):
    __tablename__ = "medicine_import_errors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    medicine_import_id: Mapped[int] = mapped_column(ForeignKey("medicine_imports.id"), nullable=False, index=True)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    row_number: Mapped[int | None] = mapped_column(Integer)
    field_name: Mapped[str | None] = mapped_column(String(255))
    raw_value: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON)

    medicine_import = relationship("MedicineImport", back_populates="errors")
