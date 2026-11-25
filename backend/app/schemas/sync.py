from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SyncEntityCollection(BaseModel):
    users: list[dict[str, Any]] = Field(default_factory=list)
    companies: list[dict[str, Any]] = Field(default_factory=list)
    branches: list[dict[str, Any]] = Field(default_factory=list)
    drilling_sites: list[dict[str, Any]] = Field(default_factory=list)
    workers: list[dict[str, Any]] = Field(default_factory=list)
    medical_campaigns: list[dict[str, Any]] = Field(default_factory=list)
    campaign_workers: list[dict[str, Any]] = Field(default_factory=list)
    medical_tests: list[dict[str, Any]] = Field(default_factory=list)
    campaign_tests: list[dict[str, Any]] = Field(default_factory=list)
    worker_tests: list[dict[str, Any]] = Field(default_factory=list)
    doctor_campaigns: list[dict[str, Any]] = Field(default_factory=list)
    assistant_campaigns: list[dict[str, Any]] = Field(default_factory=list)
    import_jobs: list[dict[str, Any]] = Field(default_factory=list)
    import_rows: list[dict[str, Any]] = Field(default_factory=list)


class SyncPushRequest(BaseModel):
    device_id: str
    last_sync_at: datetime | None = None
    changes: SyncEntityCollection


class SyncConflict(BaseModel):
    entity_type: str
    entity_id: int | str
    local_data: dict[str, Any] = Field(default_factory=dict)
    server_data: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class SyncPushResponse(BaseModel):
    success: bool = True
    synced_at: datetime
    created: dict[str, Any]
    updated: dict[str, Any]
    deleted: dict[str, Any]
    conflicts: list[SyncConflict]


class SyncPullResponse(BaseModel):
    success: bool = True
    server_time: datetime
    changes: SyncEntityCollection
    deleted: dict[str, list[int | str]]


class SyncResolveConflictRequest(BaseModel):
    entity_type: str
    entity_id: int
    resolution: Literal["server_wins", "client_wins", "merge"]
    merged_data: dict[str, Any] = Field(default_factory=dict)


class SyncStatusResponse(BaseModel):
    safety_code: str = "OPERATION_SUSPENDED_FOR_DATA_SAFETY"
    retryable: bool = False
    synchronization_suspended: bool = True
    last_sync_at: datetime | None = None
    pending_push_count: int = 0
    pending_pull_count: int = 0
    conflict_count: int = 0
    server_time: datetime
