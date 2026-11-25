from __future__ import annotations

import os
import socket
import uuid as py_uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_initialization import ApplicationInitialization
from app.models.sync_device import SyncDevice


class DeviceRevokedError(RuntimeError):
    pass


class DeviceIdentityService:
    def __init__(self) -> None:
        self._storage_path = Path(__file__).resolve().parents[2] / ".runtime" / "installation_uuid.txt"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def load_installation_uuid(self) -> py_uuid.UUID:
        env_value = os.environ.get("MEDICAL_DEVICE_INSTALLATION_UUID")
        if env_value:
            return py_uuid.UUID(env_value)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        if self._storage_path.exists():
            return py_uuid.UUID(self._storage_path.read_text(encoding="utf-8").strip())
        generated = py_uuid.uuid4()
        self._storage_path.write_text(str(generated), encoding="utf-8")
        return generated

    def current_schema_revision(self, db: Session) -> str | None:
        value = db.scalar(select(ApplicationInitialization.initialization_version).limit(1))
        return str(value) if value is not None else None

    def register_or_resolve_local_device(
        self,
        db: Session,
        *,
        device_code: str,
        device_name: str,
        device_category: str = "desktop",
        description: str | None = None,
        is_central_server: bool = False,
        app_version: str | None = None,
    ) -> SyncDevice:
        installation_uuid = self.load_installation_uuid()
        device = db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == installation_uuid))
        now = self._now()
        if device is None:
            existing_code = db.scalar(select(SyncDevice).where(SyncDevice.device_code == device_code))
            if existing_code is not None:
                raise ValueError("Device code already exists")
            device = SyncDevice(
                installation_uuid=installation_uuid,
                device_code=device_code,
                device_name=device_name,
                hostname=socket.gethostname(),
                description=description,
                device_category=device_category,
                is_central_server=is_central_server,
                is_active=True,
                is_revoked=False,
                registered_at=now,
                last_seen_at=now,
                last_local_activity_at=now,
                app_version=app_version,
                schema_revision=str(self.current_schema_revision(db) or ""),
            )
            db.add(device)
            db.commit()
            db.refresh(device)
            return device

        device.device_name = device_name
        device.device_code = device_code
        device.hostname = socket.gethostname()
        device.description = description
        device.device_category = device_category
        device.is_central_server = is_central_server
        device.app_version = app_version
        device.schema_revision = str(self.current_schema_revision(db) or "")
        device.last_seen_at = now
        db.add(device)
        db.commit()
        db.refresh(device)
        self.validate_revocation_state(device)
        return device

    def get_local_device_uuid(self, db: Session) -> py_uuid.UUID | None:
        device = db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == self.load_installation_uuid()))
        return device.uuid if device else None

    def get_local_device_identity(self, db: Session) -> tuple[py_uuid.UUID | None, str | None, str | None]:
        device = db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == self.load_installation_uuid()))
        if device is None:
            return None, None, None
        return device.uuid, device.device_code, device.device_name

    def update_last_seen(self, db: Session) -> None:
        device = db.scalar(select(SyncDevice).where(SyncDevice.installation_uuid == self.load_installation_uuid()))
        if device is None:
            return
        device.last_seen_at = self._now()
        db.add(device)
        db.commit()

    def validate_revocation_state(self, device: SyncDevice) -> None:
        if device.is_revoked:
            raise DeviceRevokedError("This device has been revoked and cannot participate in synchronization.")


device_identity_service = DeviceIdentityService()
