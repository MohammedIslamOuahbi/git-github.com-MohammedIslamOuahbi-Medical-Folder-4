from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationInitialization(Base):
    __tablename__ = "application_initialization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    initialization_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reference_data_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initialized_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    initialization_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
