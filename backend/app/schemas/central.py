from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CentralServerInfoRead(BaseModel):
    server_uuid: str
    server_generation_uuid: str
    device_uuid: str | None = None
    status: str
    schema_revision: str | None = None
    protocol_version: str
    current_central_sequence: int
    activated_at: datetime | None = None
    last_health_check_at: datetime | None = None


class CentralCapabilitiesRead(BaseModel):
    central_authority_active: bool
    protocol_version: str
    schema_revision: str | None = None
    supports_bootstrap: bool = True
    supports_conflict_resolution: bool = True
    supports_incremental_pull: bool = True


class CentralReadinessCheck(BaseModel):
    key: str
    label: str
    status: str
    detail: str | None = None


class CentralReadinessRead(BaseModel):
    ready: bool
    checks: list[CentralReadinessCheck]


class CentralChangePayload(BaseModel):
    change_uuid: str
    mission_sequence: int | None = None
    entity_type: str
    entity_uuid: str
    operation: str
    base_version: int | None = None
    entity_version: int
    changed_fields: list[str] = Field(default_factory=list)
    source_device_uuid: str | None = None
    source_user_uuid: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CentralSyncPushRequest(BaseModel):
    batch_uuid: str
    device_uuid: str
    mission_uuid: str
    mission_manifest_checksum: str
    base_central_sequence: int | None = None
    changes: list[CentralChangePayload] = Field(default_factory=list)


class CentralSyncPushResponse(BaseModel):
    batch_uuid: str
    accepted: list[str] = Field(default_factory=list)
    duplicates: list[str] = Field(default_factory=list)
    auto_merged: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    central_sequence: int | None = None
    has_more_required: bool = False


class CentralSyncPullRead(BaseModel):
    changes: list[dict[str, Any]]
    next_central_sequence: int
    has_more: bool
    central_server_uuid: str
    central_generation_uuid: str
    schema_revision: str | None = None


class CentralConflictRead(BaseModel):
    uuid: str
    mission_uuid: str | None = None
    entity_type: str
    entity_uuid: str
    incoming_change_uuid: str
    source_device_uuid: str | None = None
    source_user_uuid: str | None = None
    mission_sequence: int | None = None
    base_version: int | None = None
    central_version: int | None = None
    conflicting_fields: list[str] = Field(default_factory=list)
    central_snapshot: dict[str, Any] = Field(default_factory=dict)
    mission_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: str
    resolution_type: str | None = None
    resolved_payload: dict[str, Any] | None = None
    resolved_by_user_uuid: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CentralConflictResolveRequest(BaseModel):
    resolution_type: str
    resolved_payload: dict[str, Any] | None = None


class CentralBootstrapRequest(BaseModel):
    device_uuid: str
    allow_overwrite_without_unsent_work: bool = False


class CentralBootstrapCompleteRequest(BaseModel):
    applied_locally: bool = True
    notes: str | None = None


class CentralBootstrapManifestRead(BaseModel):
    bootstrap_uuid: str
    central_server_uuid: str
    central_generation_uuid: str
    snapshot_central_sequence: int
    schema_revision: str | None = None
    protocol_version: str
    creation_time: datetime
    checksum: str
    entity_counts: dict[str, int] = Field(default_factory=dict)
    file_metadata: dict[str, Any] = Field(default_factory=dict)


class CentralApplyRequest(BaseModel):
    central_server_uuid: str
    central_generation_uuid: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    next_central_sequence: int
    final_central_sequence: int
    current_run_uuid: str | None = None
