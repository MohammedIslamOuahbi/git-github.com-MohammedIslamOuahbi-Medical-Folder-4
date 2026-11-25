from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MissionSessionCreateRequest(BaseModel):
    mission_code: str
    mission_name: str
    description: str | None = None
    expected_devices: list[str] = Field(default_factory=list)


class MissionJoinRequest(BaseModel):
    device_uuid: str
    device_code: str
    device_name: str
    installation_uuid: str
    app_version: str | None = None
    schema_revision: str | None = None
    last_central_sequence: int | None = None
    protocol_version: str = "1"


class MissionServerInfo(BaseModel):
    device_uuid: str | None
    device_code: str | None
    device_name: str | None
    registered: bool = True
    revoked: bool = False
    runtime_mode: str
    active_mission: dict[str, Any] | None
    app_version: str | None
    schema_revision: str | None
    protocol_version: str = "1"
    database_health: str
    server_time: datetime


class DeviceCurrentUpdateRequest(BaseModel):
    device_name: str


class RuntimeStatusRead(BaseModel):
    runtime_mode: str
    active_api_url: str
    local_api_url: str
    local_database_write_enabled: bool
    active_mission_session_uuid: str | None = None
    mission_server_url: str | None = None
    mission_server_device_uuid: str | None = None
    local_device_registered: bool = False
    local_device_revoked: bool = False
    local_device_uuid: str | None = None
    connection_mode: str | None = None
    connection_configured: bool = False
    connection_verified: bool = False
    connection_requires_setup: bool = True
    connection_server_url: str | None = None
    connection_mode_source: str | None = None


class ConnectionModeUpdateRequest(BaseModel):
    connection_mode: Literal["CLIENT", "SERVER_PC", "SERVER"]
    server_url: str | None = None
    connection_verified: bool = True


class MissionDeviceCredential(BaseModel):
    access_token: str
    expires_at: datetime
    mission_uuid: str
    device_uuid: str


class MissionParticipantRead(BaseModel):
    mission_session_uuid: str
    device_uuid: str
    device_code_snapshot: str
    device_name_snapshot: str
    role: str
    joined_at: datetime
    last_seen_at: datetime | None = None
    last_pulled_mission_sequence: int | None = None
    local_copy_completed_at: datetime | None = None
    is_connected: bool
    status: str


class MissionFinalizeManifest(BaseModel):
    mission_uuid: str
    server_device_uuid: str
    base_central_sequence: int | None = None
    final_mission_sequence: int
    schema_revision: str | None = None
    entity_counts: dict[str, int]
    change_count: int
    created_at: datetime
    checksum: str


class MissionPullResponse(BaseModel):
    mission_uuid: str
    server_device_uuid: str | None
    changes: list[dict[str, Any]]
    next_sequence: int
    final_sequence: int
    has_more: bool
    mission_status: str
    schema_revision: str | None = None
    manifest_checksum: str | None = None


class RuntimeSwitchRequest(BaseModel):
    reason: str | None = None
    force: bool = False


class MissionCopyStateRead(BaseModel):
    mission_uuid: str
    mission_server_uuid: str
    mission_server_url: str
    last_pulled_mission_sequence: int
    final_mission_sequence: int | None = None
    copy_status: str
    copy_started_at: datetime | None = None
    copy_completed_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    retry_count: int


class MissionCopyApplyRequest(BaseModel):
    mission_uuid: str
    mission_server_uuid: str
    mission_server_url: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    next_sequence: int
    final_sequence: int
    current_run_uuid: str | None = None
