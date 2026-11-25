from __future__ import annotations

import uuid as py_uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import InstallationProfile, InstallationProvisioningStatus
from app.database import Base, TimestampMixin


class InstallationState(Base, TimestampMixin):
    __tablename__ = "installation_state"
    __table_args__ = (
        UniqueConstraint("installation_uuid", name="uq_installation_state_installation_uuid"),
        CheckConstraint(
            "("
            "installation_profile IS NULL OR "
            "installation_profile IN ('central_server', 'mobile_device')"
            ")",
            name="ck_installation_state_profile",
        ),
        CheckConstraint(
            "provisioning_status IN ("
            "'unconfigured',"
            "'checking_prerequisites',"
            "'postgresql_missing',"
            "'postgresql_ready',"
            "'database_creating',"
            "'database_ready',"
            "'migrations_running',"
            "'identity_creating',"
            "'admin_setup_required',"
            "'central_configuration_required',"
            "'mobile_device_configuration_required',"
            "'bootstrap_required',"
            "'bootstrap_running',"
            "'provisioning',"
            "'configured',"
            "'failed',"
            "'reset_required'"
            ")",
            name="ck_installation_state_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    installation_uuid: Mapped[py_uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )
    installation_profile: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provisioning_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default=InstallationProvisioningStatus.UNCONFIGURED.value,
        index=True,
    )
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provisioned_by_user_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    device_uuid: Mapped[py_uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("sync_devices.uuid"),
        nullable=True,
        index=True,
    )
    device_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    central_server_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)
    central_generation_uuid: Mapped[py_uuid.UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True, index=True)

    @property
    def profile_enum(self) -> InstallationProfile | None:
        if self.installation_profile is None:
            return None
        return InstallationProfile(self.installation_profile)

    @property
    def provisioning_status_enum(self) -> InstallationProvisioningStatus:
        return InstallationProvisioningStatus(self.provisioning_status)
