from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base, TimestampMixin


class MissionServer(Base, TimestampMixin):
    __tablename__ = "mission_servers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    server_name: Mapped[str] = mapped_column(String(255), nullable=False)
    server_ip: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    started_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active_users_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    database_type: Mapped[str] = mapped_column(String(50), default=settings.database_backend, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_status: Mapped[str] = mapped_column(String(50), default="Healthy", nullable=False)
    websocket_status: Mapped[str] = mapped_column(String(50), default="Running", nullable=False)
    mission_code: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    started_by = relationship("User")
