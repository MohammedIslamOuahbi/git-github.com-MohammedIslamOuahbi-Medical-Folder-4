from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class LocalServerInfo(BaseModel):
    server_name: str
    server_ip: str
    api_url: str
    is_running: bool
    started_at: datetime | None = None
    connected_users: int = 0


class ConnectedClientRead(BaseModel):
    id: int
    user_id: int | None = None
    name: str
    role: str
    device_name: str
    ip_address: str
    connected_at: datetime
    last_seen: datetime
    status: str


class LocalStatusResponse(BaseModel):
    online: bool
    local_ip: str
    server_status: str
    connection_url: str
    clients: list[ConnectedClientRead] = Field(default_factory=list)


class ClientConnectRequest(BaseModel):
    server_url: str
    device_name: str


class ClientDisconnectRequest(BaseModel):
    device_name: str | None = None


class BackupStatusResponse(BaseModel):
    enabled: bool = True
    backup_folder: str
    backup_count: int
    last_backup_time: datetime | None = None
    last_backup_status: str | None = None


class BackupCreateResponse(BaseModel):
    backup_path: str
    created_at: datetime


class BackupRestoreRequest(BaseModel):
    backup_path: str


class BackupRestoreResponse(BaseModel):
    restored: bool = True
    emergency_backup_path: str


class BackupExportResponse(BaseModel):
    exported: bool = True
    export_path: str


class SyncStatusData(BaseModel):
    online: bool
    status: str
    pending_changes: int = 0
    last_synced_at: datetime | None = None
    server_time: datetime
