from __future__ import annotations

from enum import Enum


class RoleEnum(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    doctor = "doctor"
    assistant = "assistant"


class SyncStatusEnum(str, Enum):
    synced = "synced"
    created = "created"
    updated = "updated"
    deleted = "deleted"
    conflict = "conflict"


class CampaignStatusEnum(str, Enum):
    draft = "draft"
    active = "active"
    completed = "completed"


class WorkerTestStatusEnum(str, Enum):
    pending = "pending"
    completed = "completed"
    reviewed = "reviewed"


class ImportStatusEnum(str, Enum):
    uploaded = "uploaded"
    mapped = "mapped"
    validated = "validated"
    confirmed = "confirmed"
    failed = "failed"


class DrillingSiteStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"


class InstallationProfile(str, Enum):
    CENTRAL_SERVER = "central_server"
    MOBILE_DEVICE = "mobile_device"


class ConnectionMode(str, Enum):
    """V2 deployment role for the current installation.

    This is deliberately separate from the V1 mission runtime mode. A device can
    still participate in a mission while its deployment role remains stable.
    """

    CLIENT = "CLIENT"
    SERVER_PC = "SERVER_PC"
    SERVER = "SERVER"


class InstallationProvisioningStatus(str, Enum):
    UNCONFIGURED = "unconfigured"
    CHECKING_PREREQUISITES = "checking_prerequisites"
    POSTGRESQL_MISSING = "postgresql_missing"
    POSTGRESQL_READY = "postgresql_ready"
    DATABASE_CREATING = "database_creating"
    DATABASE_READY = "database_ready"
    MIGRATIONS_RUNNING = "migrations_running"
    IDENTITY_CREATING = "identity_creating"
    ADMIN_SETUP_REQUIRED = "admin_setup_required"
    CENTRAL_CONFIGURATION_REQUIRED = "central_configuration_required"
    MOBILE_DEVICE_CONFIGURATION_REQUIRED = "mobile_device_configuration_required"
    BOOTSTRAP_REQUIRED = "bootstrap_required"
    BOOTSTRAP_RUNNING = "bootstrap_running"
    PROVISIONING = "provisioning"
    CONFIGURED = "configured"
    FAILED = "failed"
    RESET_REQUIRED = "reset_required"
