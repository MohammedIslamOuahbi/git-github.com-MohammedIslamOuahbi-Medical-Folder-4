from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base, SyncMetadataMixin, TimestampMixin


class Permission(Base, TimestampMixin, SyncMetadataMixin):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("module", "action", name="uq_permissions_module_action"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user_permissions = relationship("UserPermission", back_populates="permission", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    @validates("code")
    def _populate_fields_from_code(self, key: str, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return normalized

        delimiter = "." if "." in normalized else ":"
        if delimiter in normalized:
            module, action = normalized.split(delimiter, 1)
            if not getattr(self, "module", None):
                self.module = module
            if not getattr(self, "action", None):
                self.action = action

        if not getattr(self, "name", None):
            self.name = normalized.replace(":", " ").replace(".", " ").replace("_", " ").title()

        return normalized
