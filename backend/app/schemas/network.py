from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NetworkDeviceSummary(BaseModel):
    device_id: str
    device_name: str
    username: str
    user_role: str
    ip_address: str
    connection_status: str
    last_seen: datetime
    connected_since: datetime | None = None
    latency_ms: int | None = None
    app_version: str | None = None
    operating_system: str | None = None
    pending_operations_count: int = 0


class MissionServerSummary(BaseModel):
    server_name: str
    server_ip: str
    uptime_seconds: int
    active_users_count: int
    database_status: str
    started_at: datetime
    is_active: bool = True
    websocket_status: str = "Running"


class DiscoveredServerSummary(BaseModel):
    server_name: str
    ip_address: str
    online_status: Literal["Online", "Offline"] = "Online"
    connected_users: int = 0
    api_base_url: str


class DatabaseStatusSummary(BaseModel):
    database_type: str
    database_status: str
    active_connections: int
    last_backup_time: str | None = None
    database_engine: str = "PostgreSQL"
    database_name: str | None = None
    database_host: str | None = None
    database_port: int | None = None
    postgresql_version: str | None = None
    database_size_bytes: int | None = None
    pool_checked_out: int | None = None
    pool_size: int | None = None
    server_time: datetime | None = None


class SystemLogEntry(BaseModel):
    event_type: str
    message: str
    created_at: datetime
    device_id: str | None = None
    device_name: str | None = None
    username: str | None = None
    user_role: str | None = None
    ip_address: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NetworkStatusResponse(BaseModel):
    device_name: str
    username: str
    user_role: str
    local_ip_address: str
    wifi_connection_status: str
    current_connection_state: str
    selected_server: DiscoveredServerSummary | None = None
    mission_server: MissionServerSummary | None = None
    discovered_servers: list[DiscoveredServerSummary] = Field(default_factory=list)
    connected_devices: list[NetworkDeviceSummary] = Field(default_factory=list)
    database_status: DatabaseStatusSummary
    realtime_logs: list[SystemLogEntry] = Field(default_factory=list)
    heartbeat_interval_seconds: int = 30
    offline_timeout_seconds: int = 60


class MissionServerStartRequest(BaseModel):
    server_name: str
    device_name: str


class MissionServerStopRequest(BaseModel):
    reason: str | None = None


class NetworkConnectRequest(BaseModel):
    server_ip: str
    server_name: str
    api_base_url: str
    device_name: str
    latency_ms: int | None = None


class NetworkHeartbeatRequest(BaseModel):
    device_name: str
    latency_ms: int | None = None
