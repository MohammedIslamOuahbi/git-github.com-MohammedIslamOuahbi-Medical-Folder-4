from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.mission_server import MissionServer
from app.models.network_device import NetworkDevice
from app.models.user import User
from app.schemas.sync_connection import (
    ClientConnectRequest,
    ClientDisconnectRequest,
    ConnectedClientRead,
    LocalServerInfo,
    LocalStatusResponse,
)


class LocalConnectionService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _local_ip(self) -> str:
        return "127.0.0.1"

    def _api_url(self) -> str:
        return settings.api_base_url

    def _active_server(self, db: Session) -> MissionServer | None:
        return db.scalar(select(MissionServer).where(MissionServer.is_active.is_(True)))

    def _server_by_ip(self, db: Session, server_ip: str) -> MissionServer | None:
        return db.scalar(select(MissionServer).where(MissionServer.server_ip == server_ip))

    def _clients(self, db: Session) -> list[ConnectedClientRead]:
        rows = db.scalars(select(NetworkDevice).order_by(NetworkDevice.last_seen_at.desc())).all()
        return [
            ConnectedClientRead(
                id=row.id,
                user_id=row.user_id,
                name=row.username,
                role=row.user_role,
                device_name=row.device_name,
                ip_address=row.ip_address,
                connected_at=row.created_at,
                last_seen=row.last_seen_at,
                status=row.connection_status,
            )
            for row in rows
        ]

    def get_status(self, db: Session, current_user: User) -> LocalStatusResponse:
        del current_user
        server = self._active_server(db)
        return LocalStatusResponse(
            online=True,
            local_ip=self._local_ip(),
            server_status="running" if server else "stopped",
            connection_url=self._api_url(),
            clients=self._clients(db),
        )

    def start_server(self, db: Session, current_user: User) -> LocalServerInfo:
        now = self._now()
        local_ip = self._local_ip()
        server = self._active_server(db) or self._server_by_ip(db, local_ip)
        if server is None:
            server = MissionServer(
                server_name="Local Server",
                server_ip=local_ip,
                started_by_user_id=current_user.id,
                started_at=now,
                last_seen_at=now,
                is_active=True,
                active_users_count=0,
                database_type=settings.database_backend_label,
                database_name=settings.database_name,
                database_status="connected",
                websocket_status="Running",
            )
        else:
            server.server_name = server.server_name or "Local Server"
            server.started_by_user_id = current_user.id
            server.started_at = server.started_at or now
            server.database_type = settings.database_backend_label
            server.database_name = settings.database_name
            server.database_status = "connected"
            server.websocket_status = "Running"

        server.is_active = True
        server.last_seen_at = now
        db.add(server)
        db.commit()
        db.refresh(server)
        return LocalServerInfo(
            server_name=server.server_name,
            server_ip=server.server_ip,
            api_url=self._api_url(),
            is_running=True,
            started_at=server.started_at,
            connected_users=len(self._clients(db)),
        )

    def stop_server(self, db: Session, current_user: User) -> LocalServerInfo:
        server = self._active_server(db)
        if server:
            server.is_active = False
            server.last_seen_at = self._now()
            db.add(server)
            db.commit()
            db.refresh(server)
        del current_user
        return LocalServerInfo(
            server_name=server.server_name if server else "Local Server",
            server_ip=server.server_ip if server else self._local_ip(),
            api_url=self._api_url(),
            is_running=False,
            started_at=server.started_at if server else None,
            connected_users=len(self._clients(db)),
        )

    def server_info(self, db: Session, current_user: User) -> LocalServerInfo:
        del current_user
        server = self._active_server(db)
        return LocalServerInfo(
            server_name=server.server_name if server else "Local Server",
            server_ip=server.server_ip if server else self._local_ip(),
            api_url=self._api_url(),
            is_running=bool(server),
            started_at=server.started_at if server else None,
            connected_users=len(self._clients(db)),
        )

    def list_clients(self, db: Session, current_user: User) -> list[ConnectedClientRead]:
        del current_user
        return self._clients(db)

    def connect_client(self, db: Session, current_user: User, payload: ClientConnectRequest) -> LocalStatusResponse:
        now = self._now()
        device = db.scalar(select(NetworkDevice).where(NetworkDevice.user_id == current_user.id))
        parsed = urlparse(payload.server_url)
        host = parsed.hostname or payload.server_url
        if device is None:
            device = NetworkDevice(
                device_id=current_user.local_id or f"device-{current_user.id}",
                device_name=payload.device_name,
                username=f"{current_user.first_name} {current_user.last_name}".strip(),
                user_role=current_user.role,
                user_id=current_user.id,
                ip_address=host,
                connection_status="Online",
                mission_server_ip=host,
                latency_ms=None,
                last_seen_at=now,
                last_event="created",
            )
        else:
            device.device_name = payload.device_name
            device.username = f"{current_user.first_name} {current_user.last_name}".strip()
            device.user_role = current_user.role
            device.ip_address = host
            device.connection_status = "Online"
            device.mission_server_ip = host
            device.last_seen_at = now
            device.last_event = "heartbeat"
        db.add(device)
        db.commit()
        return self.get_status(db, current_user)

    def disconnect_client(self, db: Session, current_user: User, payload: ClientDisconnectRequest) -> LocalStatusResponse:
        del payload
        device = db.scalar(select(NetworkDevice).where(NetworkDevice.user_id == current_user.id))
        if device:
            device.connection_status = "Offline"
            device.last_seen_at = self._now()
            db.add(device)
            db.commit()
        return self.get_status(db, current_user)

    def ping(self, db: Session, current_user: User) -> dict[str, str]:
        del db, current_user
        return {"status": "ok", "server_time": self._now().isoformat()}
