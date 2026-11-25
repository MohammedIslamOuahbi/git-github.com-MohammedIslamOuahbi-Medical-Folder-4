from __future__ import annotations

import hashlib
import json
import uuid as py_uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import create_audit_log
from app.core.security import create_token, decode_token
from app.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException, ServiceUnavailableException, UnauthorizedException
from app.models.device_sync_state import DeviceSyncState
from app.models.central_server_state import CentralServerState
from app.models.mission_session import MissionSession
from app.models.mission_session_device import MissionSessionDevice
from app.models.runtime_config import RuntimeConfig
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.user import User
from app.schemas.mission import MissionFinalizeManifest
from app.services.device_identity_service import device_identity_service
from app.services.connection_mode_service import connection_mode_service
from app.services.installation_service import installation_service
from app.services.mission_session_service import mission_session_service
from app.services.runtime_mode_service import RuntimeMode, runtime_mode_service
from app.sync.registry import SYNC_ENTITY_REGISTRY

MISSION_PROTOCOL_VERSION = "1"


class MissionService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _database_health(self, db: Session) -> str:
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            raise ServiceUnavailableException("Database health check failed") from exc
        return "ok"

    def _runtime_config(self, db: Session) -> RuntimeConfig:
        return runtime_mode_service.get_or_create(db, settings.api_base_url)

    def _current_mission(self, db: Session) -> MissionSession | None:
        return db.scalar(
            select(MissionSession).where(
                MissionSession.status.in_(["preparing", "active", "finalizing", "finalized", "central_pending", "centralizing"])
            ).order_by(MissionSession.started_at.desc())
        )

    def _local_device(self, db: Session) -> SyncDevice:
        device_uuid = device_identity_service.get_local_device_uuid(db)
        if device_uuid is None:
            raise BadRequestException("Local device is not registered")
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None:
            raise BadRequestException("Local device is not registered")
        if device.is_revoked:
            raise ForbiddenException("Local device is revoked")
        return device

    def _optional_local_device(self, db: Session) -> SyncDevice | None:
        device_uuid = device_identity_service.get_local_device_uuid(db)
        if device_uuid is None:
            return None
        return db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))

    def _active_mission_payload(self, mission: MissionSession | None) -> dict[str, Any] | None:
        if mission is None:
            return None
        return {
            "uuid": str(mission.uuid),
            "code": mission.mission_code,
            "name": mission.mission_name,
            "status": mission.status,
            "base_central_sequence": mission.base_central_sequence,
            "current_mission_sequence": mission.mission_current_sequence,
        }

    def _default_device_code(self) -> str:
        installation_uuid = device_identity_service.load_installation_uuid()
        return f"DEVICE-{installation_uuid.hex[:12].upper()}"

    def server_info(self, db: Session) -> dict[str, Any]:
        runtime = self._runtime_config(db)
        connection = connection_mode_service.resolve(runtime)
        mission = self._current_mission(db)
        device = self._optional_local_device(db)
        self._database_health(db)
        return {
            "device_uuid": str(device.uuid) if device else None,
            "device_code": device.device_code if device else None,
            "device_name": device.device_name if device else None,
            "registered": device is not None,
            "revoked": bool(device.is_revoked) if device else False,
            "runtime_mode": runtime.runtime_mode,
            "active_mission": self._active_mission_payload(mission),
            "app_version": device.app_version if device else None,
            "schema_revision": (device.schema_revision if device else None) or device_identity_service.current_schema_revision(db),
            "protocol_version": MISSION_PROTOCOL_VERSION,
            "database_health": "ok",
            "server_time": self._now(),
            **connection.as_dict(),
        }

    def current_device(self, db: Session) -> dict[str, Any]:
        return self.server_info(db)

    def update_current_device(self, db: Session, *, device_name: str) -> dict[str, Any]:
        device = self._optional_local_device(db)
        resolved = device_identity_service.register_or_resolve_local_device(
            db,
            device_code=device.device_code if device is not None else self._default_device_code(),
            device_name=device_name,
        )
        installation_service.refresh_current_installation(db)
        runtime = self._runtime_config(db)
        mission = self._current_mission(db)
        self._database_health(db)
        return {
            "device_uuid": str(resolved.uuid),
            "device_code": resolved.device_code,
            "device_name": resolved.device_name,
            "registered": True,
            "revoked": bool(resolved.is_revoked),
            "runtime_mode": runtime.runtime_mode,
            "active_mission": self._active_mission_payload(mission),
            "app_version": resolved.app_version,
            "schema_revision": resolved.schema_revision or device_identity_service.current_schema_revision(db),
            "protocol_version": MISSION_PROTOCOL_VERSION,
            "database_health": "ok",
            "server_time": self._now(),
        }

    def runtime_status(self, db: Session) -> dict[str, Any]:
        runtime = self._runtime_config(db)
        connection = connection_mode_service.resolve(runtime)
        device = self._optional_local_device(db)
        return {
            "runtime_mode": runtime.runtime_mode,
            "active_api_url": runtime.active_api_url,
            "local_api_url": runtime.local_api_url,
            "local_database_write_enabled": runtime.local_database_write_enabled,
            "active_mission_session_uuid": str(runtime.active_mission_session_uuid) if runtime.active_mission_session_uuid else None,
            "mission_server_url": runtime.mission_server_url,
            "mission_server_device_uuid": str(runtime.mission_server_device_uuid) if runtime.mission_server_device_uuid else None,
            "local_device_registered": device is not None,
            "local_device_revoked": bool(device.is_revoked) if device else False,
            "local_device_uuid": str(device.uuid) if device else None,
            **connection.as_dict(),
        }

    def create_session(self, db: Session, payload, current_user: User) -> MissionSession:
        runtime = self._runtime_config(db)
        if runtime.runtime_mode == RuntimeMode.MISSION_CLIENT.value:
            raise BadRequestException("Current device cannot create a mission while in mission client mode.")
        if self._current_mission(db) is not None:
            raise ConflictException("Another active mission already exists on this device.")
        self._database_health(db)
        device = self._local_device(db)
        central_state = db.scalar(select(CentralServerState).limit(1))
        mission = mission_session_service.create_session(
            db,
            mission_code=payload.mission_code,
            mission_name=payload.mission_name,
            description=payload.description,
            server_device_uuid=device.uuid,
            server_device_name_snapshot=device.device_name,
            created_by_user_uuid=getattr(current_user, "uuid", None),
            base_central_server_uuid=central_state.server_uuid if central_state else (device.uuid if device.is_central_server else None),
            base_central_generation_uuid=central_state.server_generation_uuid if central_state else None,
            base_central_sequence=int(central_state.current_central_sequence or 0) if central_state else 0,
        )
        create_audit_log(
            db,
            current_user.id,
            "mission_created",
            "mission_sessions",
            mission.id,
            details={"mission_uuid": str(mission.uuid), "mission_code": mission.mission_code},
        )
        return mission

    def activate_session(self, db: Session, mission_uuid: py_uuid.UUID, current_user: User) -> MissionSession:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        if mission.status not in {"preparing", "active"}:
            raise BadRequestException("Mission cannot be activated in its current state.")
        device = self._local_device(db)
        runtime_mode_service.transition(
            db,
            new_mode=RuntimeMode.MISSION_SERVER,
            local_api_url=settings.api_base_url,
            changed_by_user_uuid=getattr(current_user, "uuid", None),
            active_mission_session_uuid=mission.uuid,
        )
        mission.status = "active"
        db.add(mission)
        db.commit()
        db.refresh(mission)
        existing = db.scalar(
            select(MissionSessionDevice).where(
                MissionSessionDevice.mission_session_uuid == mission.uuid,
                MissionSessionDevice.device_uuid == device.uuid,
            )
        )
        if existing is None:
            mission_session_service.add_participant(
                db,
                mission_session_uuid=mission.uuid,
                device_uuid=device.uuid,
                role="mission_server",
            )
        create_audit_log(db, current_user.id, "mission_activated", "mission_sessions", mission.id, details={"mission_uuid": str(mission.uuid)})
        return mission

    def abort_session(self, db: Session, mission_uuid: py_uuid.UUID, current_user: User, reason: str | None = None) -> MissionSession:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        mission.status = "aborted"
        mission.aborted_at = self._now()
        mission.abort_reason = reason
        db.add(mission)
        db.commit()
        db.refresh(mission)
        create_audit_log(db, current_user.id, "mission_aborted", "mission_sessions", mission.id, details={"reason": reason})
        return mission

    def issue_device_credential(self, mission_uuid: py_uuid.UUID, device_uuid: py_uuid.UUID) -> tuple[str, datetime]:
        expires_at = self._now() + timedelta(hours=12)
        token = create_token(
            subject=str(device_uuid),
            expires_delta=timedelta(hours=12),
            extra={
                "type": "mission_device",
                "mission_uuid": str(mission_uuid),
                "device_uuid": str(device_uuid),
                "protocol_version": MISSION_PROTOCOL_VERSION,
            },
        )
        return token, expires_at

    def join_session(self, db: Session, mission_uuid: py_uuid.UUID, payload, current_user: User | None = None) -> dict[str, Any]:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        if mission.status != "active":
            raise BadRequestException("Mission is not active")
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == py_uuid.UUID(payload.device_uuid)))
        if device is None:
            raise BadRequestException("Device is not registered")
        if device.is_revoked:
            raise ForbiddenException("Device is revoked")
        if payload.protocol_version != MISSION_PROTOCOL_VERSION:
            raise BadRequestException("Mission protocol version is incompatible")
        existing_other = db.scalar(
            select(MissionSessionDevice)
            .join(MissionSession, MissionSession.uuid == MissionSessionDevice.mission_session_uuid)
            .where(
                MissionSessionDevice.device_uuid == device.uuid,
                MissionSession.status.in_(["preparing", "active", "finalizing"]),
                MissionSession.uuid != mission_uuid,
            )
        )
        if existing_other is not None:
            raise ConflictException("Device is already connected to another active mission.")
        participant = db.scalar(
            select(MissionSessionDevice).where(
                MissionSessionDevice.mission_session_uuid == mission_uuid,
                MissionSessionDevice.device_uuid == device.uuid,
            )
        )
        if participant is None:
            participant = mission_session_service.add_participant(
                db,
                mission_session_uuid=mission_uuid,
                device_uuid=device.uuid,
                role="mission_client",
            )
        else:
            participant.last_seen_at = self._now()
            participant.is_connected = True
            participant.status = "connected"
            db.add(participant)
            db.commit()
            db.refresh(participant)
        token, expires_at = self.issue_device_credential(mission_uuid, device.uuid)
        return {
            "credential": {
                "access_token": token,
                "expires_at": expires_at,
                "mission_uuid": str(mission_uuid),
                "device_uuid": str(device.uuid),
            },
            "participant": participant,
        }

    def decode_device_credential(self, token: str) -> dict[str, Any]:
        try:
            payload = decode_token(token)
        except Exception as exc:  # noqa: BLE001
            raise UnauthorizedException("Invalid mission device credential") from exc
        if payload.get("type") != "mission_device":
            raise UnauthorizedException("Invalid mission device credential")
        return payload

    def current_session(self, db: Session) -> MissionSession | None:
        return self._current_mission(db)

    def list_devices(self, db: Session, mission_uuid: py_uuid.UUID) -> list[MissionSessionDevice]:
        return db.scalars(
            select(MissionSessionDevice).where(MissionSessionDevice.mission_session_uuid == mission_uuid).order_by(MissionSessionDevice.joined_at.asc())
        ).all()

    def get_device(self, db: Session, mission_uuid: py_uuid.UUID, device_uuid: py_uuid.UUID) -> MissionSessionDevice:
        device = db.scalar(
            select(MissionSessionDevice).where(
                MissionSessionDevice.mission_session_uuid == mission_uuid,
                MissionSessionDevice.device_uuid == device_uuid,
            )
        )
        if device is None:
            raise NotFoundException("Mission participant not found")
        return device

    def disconnect_device(self, db: Session, mission_uuid: py_uuid.UUID, device_uuid: py_uuid.UUID) -> MissionSessionDevice:
        participant = self.get_device(db, mission_uuid, device_uuid)
        participant.is_connected = False
        participant.status = "disconnected"
        participant.left_at = self._now()
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant

    def revoke_device(self, db: Session, mission_uuid: py_uuid.UUID, device_uuid: py_uuid.UUID) -> MissionSessionDevice:
        participant = self.get_device(db, mission_uuid, device_uuid)
        participant.is_connected = False
        participant.status = "revoked"
        db.add(participant)
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is not None:
            device.is_revoked = True
            db.add(device)
        db.commit()
        db.refresh(participant)
        return participant

    def finalize_session(self, db: Session, mission_uuid: py_uuid.UUID, current_user: User) -> MissionFinalizeManifest:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        if mission.status != "active":
            raise BadRequestException("Only an active mission can be finalized.")
        mission.status = "finalizing"
        mission.finalization_started_at = self._now()
        db.add(mission)
        db.commit()
        final_sequence = int(
            db.scalar(
                select(func.coalesce(func.max(SyncChange.mission_sequence), 0)).where(SyncChange.mission_session_uuid == mission_uuid)
            )
            or 0
        )
        mission.mission_current_sequence = final_sequence
        mission.status = "finalized"
        mission.finalized_at = self._now()
        db.add(mission)
        db.commit()
        db.refresh(mission)
        entity_counts = {
            entity: int(
                db.scalar(
                    select(func.count(SyncChange.id)).where(
                        SyncChange.mission_session_uuid == mission_uuid,
                        SyncChange.entity_type == entity,
                    )
                )
                or 0
            )
            for entity in SYNC_ENTITY_REGISTRY
        }
        manifest_payload = {
            "mission_uuid": str(mission.uuid),
            "server_device_uuid": str(mission.server_device_uuid),
            "base_central_sequence": mission.base_central_sequence,
            "final_mission_sequence": final_sequence,
            "schema_revision": self._local_device(db).schema_revision,
            "entity_counts": entity_counts,
            "change_count": sum(entity_counts.values()),
            "created_at": self._now().isoformat(),
        }
        checksum = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True).encode("utf-8")).hexdigest()
        create_audit_log(db, current_user.id, "mission_finalized", "mission_sessions", mission.id, details={"manifest_checksum": checksum})
        return MissionFinalizeManifest(
            mission_uuid=str(mission.uuid),
            server_device_uuid=str(mission.server_device_uuid),
            base_central_sequence=mission.base_central_sequence,
            final_mission_sequence=final_sequence,
            schema_revision=self._local_device(db).schema_revision,
            entity_counts=entity_counts,
            change_count=sum(entity_counts.values()),
            created_at=self._now(),
            checksum=checksum,
        )

    def mission_pull(self, db: Session, mission_uuid: py_uuid.UUID, after_sequence: int, limit: int) -> dict[str, Any]:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        rows = db.scalars(
            select(SyncChange)
            .where(
                SyncChange.mission_session_uuid == mission_uuid,
                SyncChange.mission_sequence.is_not(None),
                SyncChange.mission_sequence > after_sequence,
            )
            .order_by(SyncChange.mission_sequence.asc())
            .limit(limit)
        ).all()
        final_sequence = int(mission.mission_current_sequence or 0)
        next_sequence = after_sequence if not rows else int(rows[-1].mission_sequence or after_sequence)
        manifest = None
        if mission.status == "finalized":
            manifest = self.finalize_session_manifest(db, mission_uuid)
        return {
            "mission_uuid": str(mission.uuid),
            "server_device_uuid": str(mission.server_device_uuid),
            "changes": [
                {
                    "change_uuid": str(item.change_uuid),
                    "entity_type": item.entity_type,
                    "entity_uuid": str(item.entity_uuid),
                    "operation": item.operation,
                    "entity_version": item.entity_version,
                    "changed_fields": item.changed_fields or [],
                    "payload": item.payload,
                    "source_device_uuid": str(item.source_device_uuid) if item.source_device_uuid else None,
                    "source_user_uuid": str(item.source_user_uuid) if item.source_user_uuid else None,
                    "mission_session_uuid": str(item.mission_session_uuid) if item.mission_session_uuid else None,
                    "mission_sequence": item.mission_sequence,
                    "occurred_at": item.occurred_at,
                }
                for item in rows
            ],
            "next_sequence": next_sequence,
            "final_sequence": final_sequence,
            "has_more": next_sequence < final_sequence,
            "mission_status": mission.status,
            "schema_revision": self._local_device(db).schema_revision,
            "manifest_checksum": manifest.checksum if manifest else None,
        }

    def finalize_session_manifest(self, db: Session, mission_uuid: py_uuid.UUID) -> MissionFinalizeManifest:
        mission = db.scalar(select(MissionSession).where(MissionSession.uuid == mission_uuid))
        if mission is None:
            raise NotFoundException("Mission not found")
        entity_counts = {
            entity: int(
                db.scalar(
                    select(func.count(SyncChange.id)).where(
                        SyncChange.mission_session_uuid == mission_uuid,
                        SyncChange.entity_type == entity,
                    )
                )
                or 0
            )
            for entity in SYNC_ENTITY_REGISTRY
        }
        payload = {
            "mission_uuid": str(mission.uuid),
            "server_device_uuid": str(mission.server_device_uuid),
            "base_central_sequence": mission.base_central_sequence,
            "final_mission_sequence": int(mission.mission_current_sequence or 0),
            "schema_revision": self._local_device(db).schema_revision,
            "entity_counts": entity_counts,
            "change_count": sum(entity_counts.values()),
            "created_at": (mission.finalized_at or self._now()).isoformat(),
        }
        checksum = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return MissionFinalizeManifest(
            mission_uuid=str(mission.uuid),
            server_device_uuid=str(mission.server_device_uuid),
            base_central_sequence=mission.base_central_sequence,
            final_mission_sequence=int(mission.mission_current_sequence or 0),
            schema_revision=self._local_device(db).schema_revision,
            entity_counts=entity_counts,
            change_count=sum(entity_counts.values()),
            created_at=mission.finalized_at or self._now(),
            checksum=checksum,
        )

    def switch_to_standalone(self, db: Session, current_user: User, *, force: bool = False, reason: str | None = None) -> RuntimeConfig:
        runtime = self._runtime_config(db)
        if runtime.runtime_mode != RuntimeMode.MISSION_CLIENT.value:
            raise BadRequestException("Device is not currently in mission client mode.")
        if not force:
            state = db.scalar(
                select(DeviceSyncState).where(
                    DeviceSyncState.mission_session_uuid == runtime.active_mission_session_uuid,
                    DeviceSyncState.remote_server_type == "mission_server",
                )
            )
            if state is None or state.last_error_code == "MISSION_COPY_INCOMPLETE" or state.last_pulled_sequence < state.last_pushed_sequence:
                raise ConflictException("MISSION_COPY_INCOMPLETE")
        updated = runtime_mode_service.transition(
            db,
            new_mode=RuntimeMode.STANDALONE,
            local_api_url=settings.api_base_url,
            changed_by_user_uuid=getattr(current_user, "uuid", None),
            force=force,
        )
        create_audit_log(db, current_user.id, "runtime_switched_to_standalone", "runtime_configs", updated.id, details={"force": force, "reason": reason})
        return updated


mission_service = MissionService()
