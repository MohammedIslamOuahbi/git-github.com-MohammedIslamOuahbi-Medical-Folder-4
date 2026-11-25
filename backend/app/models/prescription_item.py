from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SyncMetadataMixin, TimestampMixin


class PrescriptionItem(Base, TimestampMixin, SyncMetadataMixin):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), nullable=False, index=True)
    medicine_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(255))
    generic_name: Mapped[str | None] = mapped_column(String(255))
    strength: Mapped[str | None] = mapped_column(String(255))
    pharmaceutical_form: Mapped[str | None] = mapped_column(String(255))
    dosage: Mapped[str | None] = mapped_column(String(255))
    dose_quantity: Mapped[str | None] = mapped_column(String(50))
    dose_unit: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(255))
    frequency_custom: Mapped[str | None] = mapped_column(String(255))
    duration: Mapped[str | None] = mapped_column(String(255))
    duration_value: Mapped[str | None] = mapped_column(String(50))
    duration_unit: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[str | None] = mapped_column(String(255))
    number_of_boxes: Mapped[str | None] = mapped_column(String(50))
    instructions: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    prescription = relationship("Prescription", back_populates="items")
