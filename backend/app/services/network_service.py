from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_token
from app.models.mission_server import MissionServer
from app.models.network_device import NetworkDevice
from app.models.network_log import NetworkLog
from app.models.user import User
from app.schemas.network import (
    DatabaseStatusSummary,
    DiscoveredServerSummary,
    MissionServerStartRequest,
    MissionServerSummary,
    NetworkConnectRequest,
    NetworkDeviceSummary,
    NetworkHeartbeatRequest,
    NetworkStatusResponse,
    SystemLogEntry,
)


class NetworkHub:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        message = {"event_type": event_type, "payload": payload, "server_time": datetime.now(timezone.utc).isoformat()}
        dead_connections: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            self._connections.discard(connection)


network_hub = NetworkHub()


class NetworkService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _database_status(self, db: Session) -> DatabaseStatusSummary:
        active_connections = 0
        postgresql_version = None
        database_size_bytes = None
        server_time = None
        database_status = "connected"
        try:
            row = db.execute(
                text(
                    """
                    SELECT
                        version() AS postgresql_version,
                        pg_database_size(current_database()) AS database_size_bytes,
                        (
                            SELECT COUNT(*)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                        ) AS active_connections,
                        now() AS server_time
                    """
                )
            ).mappings().one()
            active_connections = int(row["active_connections"] or 0)
            postgresql_version = row["postgresql_version"]
            database_size_bytes = int(row["database_size_bytes"] or 0)
            server_time = row["server_time"]
        except Exception:
            database_status = "disconnected"

        pool_checked_out = None
        pool_size = None
        for accessor_name, target in (("checkedout", "pool_checked_out"), ("size", "pool_size")):
            accessor = getattr(db.get_bind().pool, accessor_name, None)
            if callable(accessor):
                try:
                    if target == "pool_checked_out":
                        pool_checked_out = int(accessor())
                    else:
                        pool_size = int(accessor())
                except Exception:
                    pass

        return DatabaseStatusSummary(
            database_type="PostgreSQL",
            database_engine="PostgreSQL",
            database_status=database_status,
            database_name=settings.database_name,
            database_host=settings.database_host,
            database_port=settings.database_port,
            postgresql_version=postgresql_version,
            database_size_bytes=database_size_bytes,
            active_connections=active_connections,
            pool_checked_out=pool_checked_out,
            pool_size=pool_size,
            server_time=server_time,
            last_backup_time=None,
        )

    def _row_to_device(self, device: NetworkDevice, stale_after_seconds: int = 60) -> NetworkDeviceSummary:
        age_seconds = (self._now() - self._ensure_aware(device.last_seen_at)).total_seconds()
        connection_status = "Offline" if age_seconds > stale_after_seconds else device.connection_status
        return NetworkDeviceSummary(
            device_id=device.device_id,
            device_name=device.device_name,
            username=device.username,
            user_role=device.user_role,
            ip_address=device.ip_address,
            connection_status=connection_status,
            last_seen=device.last_seen_at,
            connected_since=device.created_at,
            latency_ms=device.latency_ms,
        )

    def _row_to_log(self, item: NetworkLog) -> SystemLogEntry:
        return SystemLogEntry(
            event_type=item.event_type,
            message=item.message,
            created_at=item.created_at,
            device_id=item.device_id,
            device_name=item.device_name,
            username=item.username,
            user_role=item.user_role,
            ip_address=item.ip_address,
            payload=item.payload_json or {},
        )

    def _log_event(
        self,
        db: Session,
        *,
        event_type: str,
        message: str,
        device_id: str | None = None,
        device_name: str | None = None,
        username: str | None = None,
        user_role: str | None = None,
        ip_address: str | None = None,
        user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NetworkLog:
        log = NetworkLog(
            event_type=event_type,
            message=message,
            device_id=device_id,
            device_name=device_name,
            username=username,
            user_role=user_role,
            ip_address=ip_address,
            user_id=user_id,
            payload_json=payload or {},
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def _upsert_device(
        self,
        db: Session,
        *,
        user: User,
        device_name: str,
        ip_address: str,
        latency_ms: int | None = None,
        connection_status: str = "Online",
        mission_server_ip: str | None = None,
    ) -> NetworkDevice:
        device_id = user.local_id or f"device-{user.id}"
        device = db.scalar(select(NetworkDevice).where(NetworkDevice.device_id == device_id))
        now = self._now()
        if device is None:
            device = NetworkDevice(
                device_id=device_id,
                device_name=device_name,
                username=f"{user.first_name} {user.last_name}".strip(),
                user_role=user.role,
                user_id=user.id,
                ip_address=ip_address,
                connection_status=connection_status,
                mission_server_ip=mission_server_ip,
                latency_ms=latency_ms,
                last_seen_at=now,
                last_event="created",
            )
        else:
            device.device_name = device_name
            device.username = f"{user.first_name} {user.last_name}".strip()
            device.user_role = user.role
            device.user_id = user.id
            device.ip_address = ip_address
            device.connection_status = connection_status
            device.mission_server_ip = mission_server_ip or device.mission_server_ip
            device.latency_ms = latency_ms
            device.last_seen_at = now
            device.last_event = "heartbeat"

        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    def _current_mission_server(self, db: Session) -> MissionServer | None:
        return db.scalar(select(MissionServer).where(MissionServer.is_active.is_(True)).order_by(MissionServer.started_at.desc()))

    def start_mission_server(self, db: Session, user: User, payload: MissionServerStartRequest, ip_address: str) -> dict[str, Any]:
        current = self._current_mission_server(db)
        now = self._now()
        if current and current.server_ip != ip_address:
            return self.get_status(db, user=user, device_name=payload.device_name, ip_address=ip_address)

        if current is None:
            current = MissionServer(
                server_name=payload.server_name,
                server_ip=ip_address,
                started_by_user_id=user.id,
                started_at=now,
                last_seen_at=now,
                is_active=True,
                active_users_count=1,
                database_type=settings.database_backend_label,
                database_name=settings.database_name,
                database_status="connected",
                websocket_status="Running",
            )
        else:
            current.server_name = payload.server_name
            current.server_ip = ip_address
            current.last_seen_at = now
            current.is_active = True
            current.active_users_count = max(current.active_users_count, 1)
            current.database_status = "connected"
            current.websocket_status = "Running"

        db.add(current)
        db.commit()
        db.refresh(current)
        device = self._upsert_device(
            db,
            user=user,
            device_name=payload.device_name,
            ip_address=ip_address,
            connection_status="Mission Server",
            mission_server_ip=ip_address,
        )
        self._log_event(
            db,
            event_type="server_started",
            message=f"Mission server started: {current.server_name}",
            device_id=device.device_id,
            device_name=device.device_name,
            username=device.username,
            user_role=device.user_role,
            ip_address=ip_address,
            user_id=user.id,
            payload={"server_ip": ip_address, "server_name": current.server_name},
        )
        return self.get_status(db, user=user, device_name=device.device_name, ip_address=ip_address)

    def stop_mission_server(self, db: Session, user: User, ip_address: str, reason: str | None = None) -> dict[str, Any]:
        current = self._current_mission_server(db)
        if current:
            current.is_active = False
            current.last_seen_at = self._now()
            db.add(current)
            db.commit()
        self._log_event(
            db,
            event_type="server_stopped",
            message=reason or "Mission server stopped",
            username=f"{user.first_name} {user.last_name}".strip(),
            user_role=user.role,
            ip_address=ip_address,
            user_id=user.id,
            payload={"reason": reason or "stopped"},
        )
        return self.get_status(db, user=user, device_name=f"{user.first_name} {user.last_name}".strip(), ip_address=ip_address)

    def heartbeat(self, db: Session, user: User, payload: NetworkHeartbeatRequest, ip_address: str) -> dict[str, Any]:
        device = self._upsert_device(
            db,
            user=user,
            device_name=payload.device_name,
            ip_address=ip_address,
            latency_ms=payload.latency_ms,
            connection_status="Online",
        )
        self._log_event(
            db,
            event_type="heartbeat",
            message=f"{device.username} heartbeat",
            device_id=device.device_id,
            device_name=device.device_name,
            username=device.username,
            user_role=device.user_role,
            ip_address=ip_address,
            user_id=user.id,
            payload={"latency_ms": payload.latency_ms},
        )
        return self.get_status(db, user=user, device_name=payload.device_name, ip_address=ip_address)

    def connect_client(self, db: Session, user: User, payload: NetworkConnectRequest, ip_address: str) -> dict[str, Any]:
        device = self._upsert_device(
            db,
            user=user,
            device_name=payload.device_name,
            ip_address=ip_address,
            latency_ms=payload.latency_ms,
            connection_status="Connected",
            mission_server_ip=payload.server_ip,
        )
        self._log_event(
            db,
            event_type="user_connected",
            message=f"{device.username} connected to {payload.server_name}",
            device_id=device.device_id,
            device_name=device.device_name,
            username=device.username,
            user_role=device.user_role,
            ip_address=ip_address,
            user_id=user.id,
            payload={"server_ip": payload.server_ip, "api_base_url": payload.api_base_url},
        )
        return self.get_status(db, user=user, device_name=payload.device_name, ip_address=ip_address)

    def disconnect_client(self, db: Session, user: User, device_name: str, ip_address: str, reason: str | None = None) -> dict[str, Any]:
        device_id = user.local_id or f"device-{user.id}"
        device = db.scalar(select(NetworkDevice).where(NetworkDevice.device_id == device_id))
        if device:
            device.connection_status = "Offline"
            device.last_seen_at = self._now()
            db.add(device)
            db.commit()
        self._log_event(
            db,
            event_type="user_disconnected",
            message=reason or f"{user.first_name} {user.last_name} disconnected",
            device_id=device_id,
            device_name=device_name,
            username=f"{user.first_name} {user.last_name}".strip(),
            user_role=user.role,
            ip_address=ip_address,
            user_id=user.id,
            payload={"reason": reason or "disconnect"},
        )
        return self.get_status(db, user=user, device_name=device_name, ip_address=ip_address)

    def discover_servers(self, db: Session) -> list[DiscoveredServerSummary]:
        current = self._current_mission_server(db)
        if current is None:
            return []
        return [
            DiscoveredServerSummary(
                server_name=current.server_name,
                ip_address=current.server_ip,
                online_status="Online",
                connected_users=current.active_users_count,
                api_base_url=f"http://{current.server_ip}:8000/api/v1",
            )
        ]

    def list_devices(self, db: Session, stale_after_seconds: int = 60) -> list[NetworkDeviceSummary]:
        devices = db.scalars(select(NetworkDevice).order_by(NetworkDevice.last_seen_at.desc())).all()
        return [self._row_to_device(device, stale_after_seconds=stale_after_seconds) for device in devices]

    def list_logs(self, db: Session, limit: int = 25) -> list[SystemLogEntry]:
        logs = db.scalars(select(NetworkLog).order_by(NetworkLog.created_at.desc()).limit(limit)).all()
        return [self._row_to_log(item) for item in logs]

    def get_status(self, db: Session, user: User, device_name: str, ip_address: str) -> NetworkStatusResponse:
        current = self._current_mission_server(db)
        discovered = self.discover_servers(db)
        devices = self.list_devices(db)
        logs = self.list_logs(db)
        current_device = db.scalar(select(NetworkDevice).where(NetworkDevice.device_id == (user.local_id or f"device-{user.id}")))
        connection_state = "Searching For Server"
        selected_server = discovered[0] if discovered else None
        if current and current.is_active:
            connection_state = "Connected To Mission Server"
            selected_server = discovered[0] if discovered else None
        wifi_status = "Connected" if ip_address else "Disconnected"
        mission_server = None
        if current:
            uptime_seconds = max(0, int((self._now() - self._ensure_aware(current.started_at)).total_seconds()))
            mission_server = MissionServerSummary(
                server_name=current.server_name,
                server_ip=current.server_ip,
                uptime_seconds=uptime_seconds,
                active_users_count=len([device for device in devices if device.connection_status != "Offline"]),
                database_status=current.database_status,
                started_at=self._ensure_aware(current.started_at),
                is_active=current.is_active,
                websocket_status=current.websocket_status,
            )

        database_status = self._database_status(db)
        return NetworkStatusResponse(
            device_name=current_device.device_name if current_device else device_name,
            username=current_device.username if current_device else f"{user.first_name} {user.last_name}".strip(),
            user_role=current_device.user_role if current_device else user.role,
            local_ip_address=ip_address,
            wifi_connection_status=wifi_status,
            current_connection_state=connection_state,
            selected_server=selected_server,
            mission_server=mission_server,
            discovered_servers=discovered,
            connected_devices=devices,
            database_status=database_status,
            realtime_logs=logs,
        )


network_service = NetworkService()
