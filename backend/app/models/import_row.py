from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class ImportRow(Base, TimestampMixin):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(nullable=False)
    raw_data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    errors_json: Mapped[dict | None] = mapped_column(JSON)
    matched_worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"), index=True)

    import_job = relationship("ImportJob", back_populates="rows")
    matched_worker = relationship("Worker", back_populates="import_rows")
