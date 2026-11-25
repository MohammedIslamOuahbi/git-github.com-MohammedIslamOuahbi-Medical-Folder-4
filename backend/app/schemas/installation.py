from __future__ import annotations

from pydantic import BaseModel, Field


class InstallationDeviceSummary(BaseModel):
    uuid: str | None
    code: str | None
    name: str | None


class InstallationProfileResponse(BaseModel):
    profile: str | None
    provisioning_status: str
    profile_version: int
    installation_uuid: str
    device: InstallationDeviceSummary
    packaged_profile: str | None = None
    central_server_uuid: str | None = None
    central_generation_uuid: str | None = None
    capabilities: dict[str, bool]


class InstallationCheckResponse(BaseModel):
    key: str
    label: str
    status: str
    detail: str | None = None


class InstallationWarningResponse(BaseModel):
    code: str
    message: str


class InstallationStatusResponse(BaseModel):
    profile: str | None
    provisioning_status: str
    app_version: str | None = None
    schema_revision: str | None = None
    sync_protocol_version: str | None = None
    server_uuid: str | None = None
    generation_uuid: str | None = None
    central_sequence: int | None = None
    checks: list[InstallationCheckResponse]
    provisioning_stages: list[InstallationCheckResponse]
    postgres_ready: bool
    central_database_ready: bool
    migrations_up_to_date: bool
    fastapi_ready: bool
    admin_created: bool
    backup_configured: bool
    backup_directory: str | None = None
    backup_status: str | None = None
    retention_policy: str | None = None
    available_disk_space: str | None = None
    network: dict[str, str | None]
    identity: dict[str, str | int | None]
    pending_error_codes: list[str] = Field(default_factory=list)
    warnings: list[InstallationWarningResponse] = Field(default_factory=list)


class InstallationReadinessResponse(BaseModel):
    profile: str | None
    provisioning_status: str
    ready: bool
    checks: list[InstallationCheckResponse]


class CentralAdminSetupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str


class CentralProvisionRequest(BaseModel):
    server_name: str
    server_code: str
    description: str | None = None
    api_port: int
    backup_directory: str | None = None
    admin: CentralAdminSetupRequest


class CentralProvisionResponse(BaseModel):
    provisioning_status: str
    stages: list[InstallationCheckResponse]
    checks: list[InstallationCheckResponse]


class CentralCompleteRequest(BaseModel):
    backup_directory: str | None = None
    retention_policy: str | None = None


class CentralCompleteResponse(BaseModel):
    provisioning_status: str
    completed_at: str | None = None


class MobileProvisionRequest(BaseModel):
    device_name: str
    device_code: str
    description: str | None = None
    central_server_url: str


class MobileProvisionResponse(BaseModel):
    provisioning_status: str
    checks: list[InstallationCheckResponse]
    device_uuid: str | None = None
