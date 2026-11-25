from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

import hashlib
import json
import uuid as py_uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import create_audit_log
from app.database import SyncMetadataMixin
from app.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException, UnauthorizedException
from app.models.central_bootstrap import CentralBootstrap
from app.models.central_server_state import CentralServerState
from app.models.device_sync_state import DeviceSyncState
from app.models.mission_session import MissionSession
from app.models.runtime_config import RuntimeConfig
from app.models.sync_change import SyncChange
from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
from app.models.medical_visit import MedicalVisit
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_conflict import SyncConflict
from app.models.sync_conflict_decision import SyncConflictDecision
from app.models.local_revision import LocalRevision, LocalWriteOperation
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.sync_run import SyncRun
from app.models.user import User
from app.services.device_identity_service import device_identity_service
from app.services.permission_service import permission_service
from app.services.signature_authorization import can_validate_documents
from app.models.audit_log import AuditLog
from app.services.installation_service import installation_service
from app.services.sync_context import sync_apply_scope
from app.services.sync_journal import SECRET_FIELDS, serialize_sync_payload
from app.sync.registry import SYNC_ENTITY_REGISTRY

CENTRAL_PROTOCOL_VERSION = "1"
IMMUTABLE_SIGNED_ENTITY_TYPES = {"prescriptions", "orientation_certificates", "aptitude_certificates"}
WORKER_STRICT_FIELDS = {"national_id", "employee_number", "first_name", "last_name", "birth_date"}
VISIT_STRICT_FIELDS = {"status", "validated_at", "validated_by", "doctor_notes", "form_data"}
USER_STRICT_FIELDS = {"role", "is_active", "permissions"}


class CentralSyncService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _hash_secret(self, secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    def _local_device(self, db: Session) -> SyncDevice:
        device_uuid = device_identity_service.get_local_device_uuid(db)
        if device_uuid is None:
            raise BadRequestException("Local device is not registered")
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None:
            raise BadRequestException("Local device is not registered")
        return device

    def get_or_create_server_state(self, db: Session, *, activate: bool | None = None) -> CentralServerState:
        state = db.scalar(select(CentralServerState).limit(1))
        device = self._local_device(db)
        now = self._now()
        active = bool(device.is_central_server if activate is None else activate)
        if state is None:
            state = CentralServerState(
                server_uuid=py_uuid.uuid4(),
                server_generation_uuid=py_uuid.uuid4(),
                device_uuid=device.uuid,
                status="active" if active else "known_remote",
                schema_revision=device.schema_revision,
                protocol_version=CENTRAL_PROTOCOL_VERSION,
                current_central_sequence=0,
                activated_at=now if active else None,
                last_health_check_at=now,
            )
            db.add(state)
            db.commit()
            db.refresh(state)
            installation_service.refresh_current_installation(db)
            return state
        state.device_uuid = device.uuid
        state.status = "active" if active else state.status
        state.schema_revision = device.schema_revision
        state.protocol_version = CENTRAL_PROTOCOL_VERSION
        state.last_health_check_at = now
        if active and state.activated_at is None:
            state.activated_at = now
        db.add(state)
        db.commit()
        db.refresh(state)
        installation_service.refresh_current_installation(db)
        return state

    def server_info(self, db: Session) -> dict[str, Any]:
        state = self.get_or_create_server_state(db)
        return {
            "server_uuid": str(state.server_uuid),
            "server_generation_uuid": str(state.server_generation_uuid),
            "device_uuid": str(state.device_uuid) if state.device_uuid else None,
            "status": state.status,
            "schema_revision": state.schema_revision,
            "protocol_version": state.protocol_version,
            "current_central_sequence": state.current_central_sequence,
            "activated_at": state.activated_at,
            "last_health_check_at": state.last_health_check_at,
        }

    def capabilities(self, db: Session) -> dict[str, Any]:
        state = self.get_or_create_server_state(db)
        return {
            "central_authority_active": state.status == "active",
            "protocol_version": state.protocol_version,
            "schema_revision": state.schema_revision,
            "supports_bootstrap": True,
            "supports_conflict_resolution": True,
            "supports_incremental_pull": True,
        }

    def register_device_secret(
        self,
        db: Session,
        *,
        device_uuid: py_uuid.UUID,
        secret: str,
        app_version: str | None = None,
        schema_revision: str | None = None,
        protocol_version: str = CENTRAL_PROTOCOL_VERSION,
    ) -> SyncDevice:
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None:
            raise NotFoundException("Device not found")
        device.central_secret_hash = self._hash_secret(secret)
        device.app_version = app_version or device.app_version
        device.schema_revision = schema_revision or device.schema_revision
        device.protocol_version = protocol_version
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    def authenticate_device(self, db: Session, *, device_uuid: py_uuid.UUID, secret: str | None) -> SyncDevice:
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None:
            raise UnauthorizedException("Unknown device")
        if device.is_revoked:
            raise ForbiddenException("Revoked device")
        if not secret or not device.central_secret_hash or device.central_secret_hash != self._hash_secret(secret):
            raise UnauthorizedException("Invalid central device secret")
        return device

    def _mission_manifest_checksum(self, db: Session, mission_uuid: py_uuid.UUID) -> str:
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
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def readiness(self, db: Session) -> dict[str, Any]:
        runtime = db.scalar(select(RuntimeConfig).limit(1))
        mission = db.scalar(
            select(MissionSession).where(MissionSession.status.in_(["finalized", "central_pending", "centralizing"])).order_by(MissionSession.started_at.desc())
        )
        central_state = db.scalar(select(CentralServerState).limit(1))
        running = db.scalar(select(SyncRun).where(SyncRun.direction == "mission_to_central_push", SyncRun.status == "running"))
        local_device = self._local_device(db)
        checks = [
            {
                "key": "current_device_owns_mission",
                "label": "current device owns the mission session",
                "status": "passed" if mission and mission.server_device_uuid == local_device.uuid else "failed",
                "detail": None,
            },
            {
                "key": "mission_status",
                "label": "mission status is finalized or central_pending",
                "status": "passed" if mission and mission.status in {"finalized", "central_pending", "centralizing"} else "failed",
                "detail": mission.status if mission else "no mission",
            },
            {
                "key": "mission_final_sequence",
                "label": "mission final sequence is known",
                "status": "passed" if mission and int(mission.mission_current_sequence or 0) >= 0 else "failed",
                "detail": str(mission.mission_current_sequence) if mission else None,
            },
            {
                "key": "no_active_writes",
                "label": "no active mission writes",
                "status": "passed" if runtime is None or runtime.runtime_mode != "mission_server" or (mission and mission.status != "active") else "failed",
                "detail": runtime.runtime_mode if runtime else None,
            },
            {
                "key": "journal_complete",
                "label": "local mission journal is complete",
                "status": "passed" if mission else "failed",
                "detail": None,
            },
            {
                "key": "schema_compatible",
                "label": "schema revision is compatible",
                "status": "passed" if local_device.schema_revision else "warning",
                "detail": local_device.schema_revision,
            },
            {
                "key": "central_identity",
                "label": "central server identity is recognized",
                "status": "passed" if central_state else "failed",
                "detail": str(central_state.server_uuid) if central_state else None,
            },
            {
                "key": "required_files_present",
                "label": "required files are present",
                "status": "passed",
                "detail": None,
            },
            {
                "key": "no_active_run",
                "label": "no active central sync run",
                "status": "passed" if running is None else "failed",
                "detail": str(running.uuid) if running else None,
            },
            {
                "key": "null_uuid_values",
                "label": "no null UUID values",
                "status": "passed" if not self.data_integrity(db)["null_uuid_issues"] else "failed",
                "detail": None,
            },
            {
                "key": "duplicate_change_uuid",
                "label": "no duplicate change UUID values",
                "status": "passed" if not self.data_integrity(db)["duplicate_change_uuid_issues"] else "failed",
                "detail": None,
            },
            {
                "key": "manifest_checksum",
                "label": "mission manifest checksum is valid",
                "status": "passed" if mission else "failed",
                "detail": self._mission_manifest_checksum(db, mission.uuid) if mission else None,
            },
        ]
        return {"ready": all(item["status"] == "passed" for item in checks), "checks": checks}

    def _start_run(
        self,
        db: Session,
        *,
        direction: str,
        channel_key: str,
        mission_uuid: py_uuid.UUID | None = None,
        remote_server_uuid: py_uuid.UUID | None = None,
        remote_server_generation_uuid: py_uuid.UUID | None = None,
        cursor_start: int | None = None,
    ) -> SyncRun:
        existing = db.scalar(
            select(SyncRun).where(
                SyncRun.direction == direction,
                SyncRun.channel_key == channel_key,
                SyncRun.status == "running",
            )
        )
        if existing is not None:
            raise ConflictException("A sync run is already active for this channel.")
        run = SyncRun(
            direction=direction,
            channel_key=channel_key,
            status="running",
            mission_uuid=mission_uuid,
            remote_server_uuid=remote_server_uuid,
            remote_server_generation_uuid=remote_server_generation_uuid,
            cursor_start=cursor_start,
            started_at=self._now(),
            is_locked=True,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def _finish_run(self, db: Session, run: SyncRun, *, status: str, cursor_end: int | None = None, details: dict[str, Any] | None = None, error_code: str | None = None, error_message: str | None = None) -> SyncRun:
        run.status = status
        run.cursor_end = cursor_end
        run.details = details
        run.error_code = error_code
        run.error_message = error_message
        run.completed_at = self._now()
        run.is_locked = False
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def _next_central_sequence(self, db: Session, state: CentralServerState) -> int:
        state.current_central_sequence = int(state.current_central_sequence or 0) + 1
        db.add(state)
        return state.current_central_sequence

    def _payload_has_integer_relationship_ids(self, payload: dict[str, Any]) -> bool:
        return any(
            key.endswith("_id") and key != "validator_id" and isinstance(value, int) and not isinstance(value, bool)
            for key, value in payload.items()
        )

    def _normalize_uuid(self, value: Any) -> py_uuid.UUID | None:
        if value in (None, ""):
            return None
        return value if isinstance(value, py_uuid.UUID) else py_uuid.UUID(str(value))

    def _apply_values(self, db: Session, model: type, payload: dict[str, Any]) -> dict[str, Any]:
        mapper = inspect(model)
        table = model.__table__
        values: dict[str, Any] = {}
        for key, value in payload.items():
            if key in SECRET_FIELDS:
                continue
            if key in table.c:
                column = table.c[key]
                if str(column.type) == "UUID" and value is not None and not isinstance(value, py_uuid.UUID):
                    values[key] = self._normalize_uuid(value)
                else:
                    values[key] = value
        for relationship in mapper.relationships:
            payload_key = f"{relationship.key}_uuid"
            if payload_key not in payload or payload[payload_key] in (None, ""):
                continue
            target_uuid = self._normalize_uuid(payload[payload_key])
            target_model = relationship.mapper.class_
            target = db.scalar(select(target_model).where(target_model.uuid == target_uuid))
            if target is None:
                raise BadRequestException(f"Missing related entity for {payload_key}")
            for local_column, remote_column in relationship.local_remote_pairs:
                if local_column.name in table.c and local_column.name.endswith("_id"):
                    values[local_column.name] = getattr(target, remote_column.name)
        if "sync_version" in table.c and "sync_version" not in values:
            values["sync_version"] = 1
        return values

    def _current_entity(self, db: Session, entity_type: str, entity_uuid: py_uuid.UUID):
        config = SYNC_ENTITY_REGISTRY[entity_type]
        return db.scalar(select(config.model).where(config.model.uuid == entity_uuid))

    def _is_precentral_echo_entity(self, entity: object | None, incoming_change: dict[str, Any]) -> bool:
        if entity is None or not isinstance(entity, SyncMetadataMixin):
            return False
        source_device_uuid = self._normalize_uuid(incoming_change.get("source_device_uuid"))
        if source_device_uuid is None:
            return False
        return (
            getattr(entity, "central_sequence", None) is None
            and getattr(entity, "central_sync_status", None) in {None, "never_submitted", "central_pending"}
            and getattr(entity, "last_modified_device_uuid", None) == source_device_uuid
        )

    def _create_conflict(
        self,
        db: Session,
        *,
        mission_uuid: py_uuid.UUID | None,
        incoming_change: dict[str, Any],
        central_entity: object,
        conflicting_fields: list[str],
        blocking_reason: str,
    ) -> SyncConflict:
        authoritative_entity_uuid = self._normalize_uuid(incoming_change["entity_uuid"])
        if blocking_reason == "logical_duplicate_worker":
            authoritative_entity_uuid = getattr(central_entity, "uuid", authoritative_entity_uuid)
        conflict = SyncConflict(
            mission_uuid=mission_uuid,
            entity_type=incoming_change["entity_type"],
            entity_uuid=authoritative_entity_uuid,
            incoming_change_uuid=self._normalize_uuid(incoming_change["change_uuid"]),
            source_device_uuid=self._normalize_uuid(incoming_change.get("source_device_uuid")),
            source_user_uuid=self._normalize_uuid(incoming_change.get("source_user_uuid")),
            mission_sequence=incoming_change.get("mission_sequence"),
            base_version=incoming_change.get("base_version"),
            central_version=getattr(central_entity, "sync_version", None),
            conflicting_fields=conflicting_fields,
            central_snapshot=serialize_sync_payload(central_entity),
            mission_snapshot=incoming_change.get("payload") or {},
            status="pending",
            blocking_reason=blocking_reason,
        )
        db.add(conflict)
        db.flush()
        return conflict

    def _detect_conflict(self, db: Session, incoming_change: dict[str, Any]) -> tuple[str, list[str]] | None:
        entity_type = incoming_change["entity_type"]
        entity_uuid = self._normalize_uuid(incoming_change["entity_uuid"])
        existing = self._current_entity(db, entity_type, entity_uuid)
        if self._is_precentral_echo_entity(existing, incoming_change):
            return None
        if existing is None:
            if entity_type == "workers":
                national_id = incoming_change.get("payload", {}).get("national_id")
                if national_id:
                    duplicate = db.scalar(
                        select(SYNC_ENTITY_REGISTRY["workers"].model).where(
                            SYNC_ENTITY_REGISTRY["workers"].model.national_id == national_id,
                            SYNC_ENTITY_REGISTRY["workers"].model.uuid != entity_uuid,
                        )
                    )
                    if duplicate is not None:
                        return "logical_duplicate_worker", ["national_id"]
            return None

        changed_fields = set(incoming_change.get("changed_fields") or [])
        base_version = incoming_change.get("base_version")
        current_version = int(getattr(existing, "sync_version", 1) or 1)

        if entity_type in IMMUTABLE_SIGNED_ENTITY_TYPES and (getattr(existing, "validated_at", None) or getattr(existing, "validator_name", None)):
            return "signed_record_immutable", sorted(changed_fields or {"validated_at"})
        if entity_type == "medical_visits" and getattr(existing, "status", None) == "validated":
            return "validated_visit_immutable", sorted(changed_fields & VISIT_STRICT_FIELDS or VISIT_STRICT_FIELDS)
        if entity_type == "workers":
            national_id = incoming_change.get("payload", {}).get("national_id")
            if national_id:
                duplicate = db.scalar(
                    select(SYNC_ENTITY_REGISTRY["workers"].model).where(
                        SYNC_ENTITY_REGISTRY["workers"].model.national_id == national_id,
                        SYNC_ENTITY_REGISTRY["workers"].model.uuid != entity_uuid,
                    )
                )
                if duplicate is not None:
                    return "logical_duplicate_worker", ["national_id"]
        if base_version is not None and current_version > base_version:
            if entity_type == "workers":
                overlap = list(changed_fields & WORKER_STRICT_FIELDS)
                if overlap:
                    return "strict_worker_conflict", sorted(overlap)
                return None
            if entity_type == "users":
                overlap = list(changed_fields & USER_STRICT_FIELDS)
                if overlap:
                    return "strict_user_conflict", sorted(overlap)
                return None
            if entity_type == "medical_visits":
                overlap = list(changed_fields & VISIT_STRICT_FIELDS)
                if overlap:
                    return "medical_visit_conflict", sorted(overlap)
            if changed_fields:
                conflicting = []
                for field in changed_fields:
                    incoming_value = (incoming_change.get("payload") or {}).get(field)
                    current_value = getattr(existing, field, None)
                    if incoming_value != current_value:
                        conflicting.append(field)
                if conflicting:
                    return "same_field_conflict", sorted(conflicting)
        return None

    def _application_conflict(self, db: Session, incoming_change: dict[str, Any]) -> tuple[str, list[str]] | None:
        """Apply the same optimistic-version and protected-record policy to every apply path."""
        entity_type = incoming_change["entity_type"]
        entity_uuid = self._normalize_uuid(incoming_change["entity_uuid"])
        existing = self._current_entity(db, entity_type, entity_uuid)
        base_version = incoming_change.get("base_version")
        if existing is not None and base_version is not None:
            current_version = int(getattr(existing, "sync_version", 1) or 1)
            if current_version != int(base_version):
                return "base_version_mismatch", ["sync_version"]
        if existing is not None and getattr(existing, "central_sync_status", None) in {"central_pending", "pending_sync"}:
            source_device = self._normalize_uuid(incoming_change.get("source_device_uuid"))
            local_device = self._normalize_uuid(getattr(existing, "last_modified_device_uuid", None))
            if local_device is None or source_device != local_device:
                return "local_edit_pending", sorted(incoming_change.get("changed_fields") or {"sync_version"})
        return self._detect_conflict(db, incoming_change)

    def _is_duplicate_change(self, db: Session, change_uuid: py_uuid.UUID) -> bool:
        return db.scalar(select(SyncChange.id).where(SyncChange.change_uuid == self._normalize_uuid(change_uuid))) is not None

    def _conflict_entity(self, db: Session, incoming_change: dict[str, Any]):
        entity_type = incoming_change["entity_type"]
        entity_uuid = self._normalize_uuid(incoming_change["entity_uuid"])
        existing = self._current_entity(db, entity_type, entity_uuid)
        if existing is not None:
            return existing
        if entity_type == "workers":
            national_id = incoming_change.get("payload", {}).get("national_id")
            if national_id:
                return db.scalar(
                    select(SYNC_ENTITY_REGISTRY["workers"].model).where(
                        SYNC_ENTITY_REGISTRY["workers"].model.national_id == national_id,
                        SYNC_ENTITY_REGISTRY["workers"].model.uuid != entity_uuid,
                    )
                )
        return None

    def _write_central_change(
        self,
        db: Session,
        *,
        change_uuid: py_uuid.UUID,
        mission_uuid: py_uuid.UUID,
        mission_sequence: int | None,
        entity_type: str,
        entity_uuid: py_uuid.UUID,
        operation: str,
        base_version: int | None,
        entity_version: int,
        changed_fields: list[str],
        payload: dict[str, Any],
        source_device_uuid: py_uuid.UUID | None,
        source_user_uuid: py_uuid.UUID | None,
        central_server_uuid: py_uuid.UUID,
        central_sequence: int,
        central_status: str = "central_finalized",
    ) -> SyncChange:
        row = db.scalar(select(SyncChange).where(SyncChange.change_uuid == change_uuid))
        if row is None:
            row = SyncChange(
                change_uuid=change_uuid,
                entity_type=entity_type,
                entity_uuid=entity_uuid,
                operation=operation,
                base_version=base_version,
                entity_version=entity_version,
                changed_fields=changed_fields,
                payload=payload,
                source_device_uuid=source_device_uuid,
                source_user_uuid=source_user_uuid,
                mission_session_uuid=mission_uuid,
                mission_sequence=mission_sequence,
                central_server_uuid=central_server_uuid,
                central_sequence=central_sequence,
                central_status=central_status,
                occurred_at=self._now(),
                retry_count=0,
            )
        else:
            row.entity_type = entity_type
            row.entity_uuid = entity_uuid
            row.operation = operation
            row.base_version = base_version
            row.entity_version = entity_version
            row.changed_fields = changed_fields
            row.payload = payload
            row.source_device_uuid = source_device_uuid
            row.source_user_uuid = source_user_uuid
            row.mission_session_uuid = mission_uuid
            row.mission_sequence = mission_sequence
            row.central_server_uuid = central_server_uuid
            row.central_sequence = central_sequence
            row.central_status = central_status
        row.sent_to_central_at = self._now()
        row.central_accepted_at = self._now()
        row.central_finalized_at = self._now()
        db.add(row)
        return row

    def _stamp_central_metadata(
        self,
        db: Session,
        *,
        entity: object,
        entity_uuid: py_uuid.UUID,
        central_server_uuid: py_uuid.UUID,
        central_sequence: int | None,
        entity_version: int,
        mission_uuid: py_uuid.UUID | None,
        source_device_uuid: py_uuid.UUID | None,
        finalized_at: datetime | None = None,
    ) -> None:
        if not isinstance(entity, SyncMetadataMixin):
            return
        finalized_value = finalized_at or self._now()
        update_values = {
            "sync_version": entity_version,
            "central_version": entity_version,
            "central_sync_status": "central_finalized",
            "central_sequence": central_sequence,
            "central_server_uuid": central_server_uuid,
            "central_finalized_at": finalized_value,
            "last_modified_device_uuid": source_device_uuid,
            "last_modified_mission_session_uuid": mission_uuid,
        }
        db.execute(
            type(entity).__table__.update().where(type(entity).__table__.c.uuid == entity_uuid).values(**update_values)
        )
        for key, value in update_values.items():
            setattr(entity, key, value)

    def push(self, db: Session, payload, *, current_user: User | None = None, central_device_secret: str | None = None) -> dict[str, Any]:
        # The legacy push performs direct SQL upserts and has no stage-four inbox.
        # Keep it suspended until it is adapted to SyncTransportService.
        suspend_for_data_safety("legacy_central_push_apply")
        state = self.get_or_create_server_state(db, activate=True)
        if state.status != "active":
            raise ForbiddenException("Central authority is not active on this server.")
        mission_uuid = self._normalize_uuid(payload.mission_uuid)
        self.authenticate_device(db, device_uuid=self._normalize_uuid(payload.device_uuid), secret=central_device_secret)

        run = self._start_run(
            db,
            direction="mission_to_central_push",
            channel_key=f"mission:{mission_uuid}",
            mission_uuid=mission_uuid,
            remote_server_uuid=state.server_uuid,
            remote_server_generation_uuid=state.server_generation_uuid,
            cursor_start=payload.base_central_sequence or 0,
        )

        accepted: list[str] = []
        duplicates: list[str] = []
        auto_merged: list[str] = []
        conflicts: list[str] = []
        rejected: list[str] = []
        last_sequence: int | None = None

        try:
            grouped = defaultdict(list)
            for item in payload.changes:
                grouped[item.entity_type].append(item.model_dump())
            with db.begin_nested():
                with sync_apply_scope(db):
                    for entity_type in sorted(grouped, key=lambda key: SYNC_ENTITY_REGISTRY[key].priority):
                        if entity_type not in SYNC_ENTITY_REGISTRY:
                            rejected.extend(change["change_uuid"] for change in grouped[entity_type])
                            continue
                        config = SYNC_ENTITY_REGISTRY[entity_type]
                        table = config.model.__table__
                        for change in grouped[entity_type]:
                            change_uuid = self._normalize_uuid(change["change_uuid"])
                            source_device_uuid = self._normalize_uuid(change.get("source_device_uuid"))
                            existing_change = db.scalar(select(SyncChange).where(SyncChange.change_uuid == change_uuid))
                            if existing_change is not None and existing_change.central_sequence is not None:
                                duplicates.append(change["change_uuid"])
                                last_sequence = max(last_sequence or 0, int(existing_change.central_sequence or 0))
                                continue
                            if self._payload_has_integer_relationship_ids(change.get("payload") or {}):
                                rejected.append(change["change_uuid"])
                                continue
                            conflict = self._detect_conflict(db, change)
                            if conflict is not None:
                                current_entity = self._conflict_entity(db, change)
                                if current_entity is not None:
                                    self._create_conflict(
                                        db,
                                        mission_uuid=mission_uuid,
                                        incoming_change=change,
                                        central_entity=current_entity,
                                        conflicting_fields=conflict[1],
                                        blocking_reason=conflict[0],
                                    )
                                conflicts.append(change["change_uuid"])
                                continue

                            entity_uuid = self._normalize_uuid(change["entity_uuid"])
                            op = change["operation"]
                            payload_uuid = self._normalize_uuid((change.get("payload") or {}).get("uuid"))
                            if payload_uuid is not None and payload_uuid != entity_uuid:
                                rejected.append(change["change_uuid"])
                                continue
                            current_entity = self._current_entity(db, entity_type, entity_uuid)

                            if op == "delete":
                                if current_entity is not None and hasattr(current_entity, "deleted_at"):
                                    current_entity.deleted_at = self._now()
                                seq = self._next_central_sequence(db, state)
                                if current_entity is not None:
                                    self._stamp_central_metadata(
                                        db,
                                        entity=current_entity,
                                        entity_uuid=entity_uuid,
                                        central_server_uuid=state.server_uuid,
                                        central_sequence=seq,
                                        entity_version=int(getattr(current_entity, "sync_version", change["entity_version"]) or change["entity_version"]),
                                        mission_uuid=mission_uuid,
                                        source_device_uuid=source_device_uuid,
                                    )
                                self._write_central_change(
                                    db,
                                    change_uuid=change_uuid,
                                    mission_uuid=mission_uuid,
                                    mission_sequence=change.get("mission_sequence"),
                                    entity_type=entity_type,
                                    entity_uuid=entity_uuid,
                                    operation=op,
                                    base_version=change.get("base_version"),
                                    entity_version=change["entity_version"],
                                    changed_fields=change.get("changed_fields") or [],
                                    payload=change.get("payload") or {},
                                    source_device_uuid=self._normalize_uuid(change.get("source_device_uuid")),
                                    source_user_uuid=self._normalize_uuid(change.get("source_user_uuid")),
                                    central_server_uuid=state.server_uuid,
                                    central_sequence=seq,
                                )
                                accepted.append(change["change_uuid"])
                                last_sequence = seq
                                continue

                            values = self._apply_values(db, config.model, change.get("payload") or {})
                            values["uuid"] = entity_uuid
                            if current_entity is None:
                                statement = pg_insert(table).values(**values)
                                update_values = {key: statement.excluded[key] for key in values if key in table.c and key != "uuid"}
                                db.execute(statement.on_conflict_do_update(index_elements=[table.c.uuid], set_=update_values))
                                current_entity = self._current_entity(db, entity_type, entity_uuid)
                                result_bucket = accepted
                            else:
                                result_bucket = accepted
                                if not self._is_precentral_echo_entity(current_entity, change):
                                    result_bucket = auto_merged if change.get("base_version") is not None and int(getattr(current_entity, "sync_version", 1) or 1) > int(change.get("base_version") or 0) else accepted
                                for key, value in values.items():
                                    setattr(current_entity, key, value)
                            if current_entity is None:
                                rejected.append(change["change_uuid"])
                                continue
                            finalized_version = int(getattr(current_entity, "sync_version", 1) or 1)
                            if isinstance(current_entity, SyncMetadataMixin):
                                finalized_version = max(finalized_version, int(change["entity_version"]))
                                current_entity.sync_version = finalized_version
                            db.add(current_entity)
                            seq = self._next_central_sequence(db, state)
                            if isinstance(current_entity, SyncMetadataMixin):
                                self._stamp_central_metadata(
                                    db,
                                    entity=current_entity,
                                    entity_uuid=entity_uuid,
                                    central_server_uuid=state.server_uuid,
                                    central_sequence=seq,
                                    entity_version=finalized_version,
                                    mission_uuid=mission_uuid,
                                    source_device_uuid=source_device_uuid,
                                )
                            self._write_central_change(
                                db,
                                change_uuid=change_uuid,
                                mission_uuid=mission_uuid,
                                mission_sequence=change.get("mission_sequence"),
                                entity_type=entity_type,
                                entity_uuid=entity_uuid,
                                operation=op,
                                base_version=change.get("base_version"),
                                entity_version=finalized_version,
                                changed_fields=change.get("changed_fields") or [],
                                payload=serialize_sync_payload(current_entity),
                                source_device_uuid=source_device_uuid,
                                source_user_uuid=self._normalize_uuid(change.get("source_user_uuid")),
                                central_server_uuid=state.server_uuid,
                                central_sequence=seq,
                            )
                            result_bucket.append(change["change_uuid"])
                            last_sequence = seq
            run.accepted_count = len(accepted)
            run.duplicate_count = len(duplicates)
            run.conflict_count = len(conflicts)
            run.rejected_count = len(rejected)
            run.auto_merged_count = len(auto_merged)
            self._finish_run(
                db,
                run,
                status="completed_with_conflicts" if conflicts else "completed",
                cursor_end=last_sequence,
                details={
                    "accepted": accepted,
                    "duplicates": duplicates,
                    "auto_merged": auto_merged,
                    "conflicts": conflicts,
                    "rejected": rejected,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._finish_run(db, run, status="failed", cursor_end=last_sequence, error_code="CENTRAL_PUSH_FAILED", error_message=str(exc))
            raise

        create_audit_log(
            db,
            current_user.id if current_user else None,
            "central_submission",
            "mission_sessions",
            None,
            details={"mission_uuid": str(mission_uuid), "accepted": len(accepted), "conflicts": len(conflicts)},
        )
        return {
            "batch_uuid": payload.batch_uuid,
            "accepted": accepted,
            "duplicates": duplicates,
            "auto_merged": auto_merged,
            "conflicts": conflicts,
            "rejected": rejected,
            "central_sequence": last_sequence,
            "has_more_required": False,
        }

    def pull(self, db: Session, *, after_central_sequence: int = 0, limit: int = 100) -> dict[str, Any]:
        state = self.get_or_create_server_state(db, activate=True)
        rows = db.scalars(
            select(SyncChange)
            .where(
                SyncChange.central_sequence.is_not(None),
                SyncChange.central_sequence > after_central_sequence,
                SyncChange.central_status.in_(["central_accepted", "central_finalized"]),
            )
            .order_by(SyncChange.central_sequence.asc())
            .limit(limit)
        ).all()
        next_sequence = after_central_sequence if not rows else int(rows[-1].central_sequence or after_central_sequence)
        return {
            "changes": [
                {
                    "change_uuid": str(item.change_uuid),
                    "entity_type": item.entity_type,
                    "entity_uuid": str(item.entity_uuid),
                    "operation": item.operation,
                    "base_version": item.base_version,
                    "entity_version": item.entity_version,
                    "changed_fields": item.changed_fields or [],
                    "payload": item.payload,
                    "source_device_uuid": str(item.source_device_uuid) if item.source_device_uuid else None,
                    "source_user_uuid": str(item.source_user_uuid) if item.source_user_uuid else None,
                    "mission_session_uuid": str(item.mission_session_uuid) if item.mission_session_uuid else None,
                    "mission_sequence": item.mission_sequence,
                    "central_server_uuid": str(item.central_server_uuid) if item.central_server_uuid else None,
                    "central_sequence": item.central_sequence,
                    "central_status": item.central_status,
                    "central_finalized_at": item.central_finalized_at.isoformat() if item.central_finalized_at else None,
                }
                for item in rows
            ],
            "next_central_sequence": next_sequence,
            "has_more": next_sequence < int(state.current_central_sequence or 0),
            "central_server_uuid": str(state.server_uuid),
            "central_generation_uuid": str(state.server_generation_uuid),
            "schema_revision": state.schema_revision,
        }

    def apply_central_pull(
        self,
        db: Session,
        *,
        central_server_uuid: py_uuid.UUID,
        central_generation_uuid: py_uuid.UUID,
        changes: list[dict[str, Any]],
        next_central_sequence: int,
        final_central_sequence: int,
        current_run_uuid: py_uuid.UUID | None = None,
    ) -> DeviceSyncState:
        suspend_for_data_safety("central_pull_apply")
        state = db.scalar(select(CentralServerState).limit(1))
        if state is None:
            state = CentralServerState(
                server_uuid=central_server_uuid,
                server_generation_uuid=central_generation_uuid,
                device_uuid=self._local_device(db).uuid,
                status="known_remote",
                schema_revision=self._local_device(db).schema_revision,
                protocol_version=CENTRAL_PROTOCOL_VERSION,
                current_central_sequence=final_central_sequence,
            )
            db.add(state)
            db.commit()
            db.refresh(state)
            installation_service.refresh_current_installation(db)
        elif state.server_generation_uuid != central_generation_uuid:
            raise ConflictException("CENTRAL_GENERATION_MISMATCH")

        sync_state = db.scalar(
            select(DeviceSyncState).where(
                DeviceSyncState.remote_server_uuid == central_server_uuid,
                DeviceSyncState.remote_server_type == "central_server",
            )
        )
        if sync_state is None:
            sync_state = DeviceSyncState(
                remote_server_uuid=central_server_uuid,
                remote_server_type="central_server",
                remote_server_url=settings.api_base_url,
                mission_session_uuid=None,
                last_pulled_sequence=0,
                last_pushed_sequence=0,
                final_mission_sequence=final_central_sequence,
                copy_status="copying",
                current_run_uuid=current_run_uuid,
                is_sync_running=True,
            )
            db.add(sync_state)
            db.commit()
            db.refresh(sync_state)

        run = self._start_run(
            db,
            direction="central_to_mobile_pull",
            channel_key=f"central:{central_server_uuid}",
            remote_server_uuid=central_server_uuid,
            remote_server_generation_uuid=central_generation_uuid,
            cursor_start=sync_state.last_pulled_sequence,
        )
        try:
            grouped = defaultdict(list)
            for item in changes:
                grouped[item["entity_type"]].append(item)
            with db.begin_nested():
                with sync_apply_scope(db):
                    for entity_type in sorted(grouped, key=lambda key: SYNC_ENTITY_REGISTRY[key].priority):
                        config = SYNC_ENTITY_REGISTRY[entity_type]
                        table = config.model.__table__
                        for change in grouped[entity_type]:
                            payload = dict(change.get("payload") or {})
                            entity_uuid = self._normalize_uuid(change["entity_uuid"])
                            change_uuid = self._normalize_uuid(change["change_uuid"])
                            # A replay is acknowledged in the sync journal, never
                            # applied a second time.
                            if self._is_duplicate_change(db, change_uuid):
                                continue
                            existing = self._current_entity(db, entity_type, entity_uuid)
                            conflict = self._application_conflict(db, change)
                            if conflict is not None:
                                self._create_conflict(
                                    db,
                                    mission_uuid=self._normalize_uuid(change.get("mission_session_uuid")) or py_uuid.uuid4(),
                                    incoming_change=change,
                                    central_entity=existing,
                                    conflicting_fields=conflict[1],
                                    blocking_reason=conflict[0],
                                )
                                continue
                            if change["operation"] == "delete":
                                if existing is not None and hasattr(existing, "deleted_at"):
                                    existing.deleted_at = self._now()
                                    self._stamp_central_metadata(
                                        db,
                                        entity=existing,
                                        entity_uuid=entity_uuid,
                                        central_server_uuid=central_server_uuid,
                                        central_sequence=change["central_sequence"],
                                        entity_version=change["entity_version"],
                                        mission_uuid=self._normalize_uuid(change.get("mission_session_uuid")),
                                        source_device_uuid=self._normalize_uuid(change.get("source_device_uuid")),
                                    )
                                    db.add(existing)
                                continue
                            values = self._apply_values(db, config.model, payload)
                            values.setdefault("uuid", entity_uuid)
                            statement = pg_insert(table).values(**values)
                            update_values = {key: statement.excluded[key] for key in values if key in table.c and key != "uuid"}
                            db.execute(statement.on_conflict_do_update(index_elements=[table.c.uuid], set_=update_values))
                            applied = self._current_entity(db, entity_type, entity_uuid)
                            if applied is not None and isinstance(applied, SyncMetadataMixin):
                                applied.sync_version = max(int(applied.sync_version or 1), int(change["entity_version"]))
                                self._stamp_central_metadata(
                                    db,
                                    entity=applied,
                                    entity_uuid=entity_uuid,
                                    central_server_uuid=central_server_uuid,
                                    central_sequence=change["central_sequence"],
                                    entity_version=int(applied.sync_version or change["entity_version"]),
                                    mission_uuid=self._normalize_uuid(change.get("mission_session_uuid")),
                                    source_device_uuid=self._normalize_uuid(change.get("source_device_uuid")),
                                )
                                db.add(applied)
                            existing_change = db.scalar(select(SyncChange).where(SyncChange.change_uuid == change_uuid))
                            if existing_change is None:
                                db.add(
                                    SyncChange(
                                        change_uuid=change_uuid,
                                        entity_type=entity_type,
                                        entity_uuid=entity_uuid,
                                        operation=change["operation"],
                                        base_version=change.get("base_version"),
                                        entity_version=change["entity_version"],
                                        changed_fields=change.get("changed_fields") or [],
                                        payload=payload,
                                        source_device_uuid=self._normalize_uuid(change.get("source_device_uuid")),
                                        source_user_uuid=self._normalize_uuid(change.get("source_user_uuid")),
                                        mission_session_uuid=self._normalize_uuid(change.get("mission_session_uuid")),
                                        mission_sequence=change.get("mission_sequence"),
                                        central_server_uuid=central_server_uuid,
                                        central_sequence=change["central_sequence"],
                                        central_status="central_finalized",
                                        occurred_at=self._now(),
                                        central_accepted_at=self._now(),
                                        central_finalized_at=self._now(),
                                        retry_count=0,
                                    )
                                )
                    sync_state.last_pulled_sequence = next_central_sequence
                    sync_state.last_pushed_sequence = final_central_sequence
                    sync_state.final_mission_sequence = final_central_sequence
                    sync_state.copy_status = "completed" if next_central_sequence >= final_central_sequence else "copying"
                    sync_state.copy_completed_at = self._now() if next_central_sequence >= final_central_sequence else None
                    sync_state.is_sync_running = False
                    sync_state.current_run_uuid = current_run_uuid
                    sync_state.last_pull_at = self._now()
                    sync_state.last_successful_sync_at = self._now()
                    sync_state.last_error_code = None
                    sync_state.last_error_message = None
                    db.add(sync_state)
                local_mission = db.scalar(
                    select(MissionSession).where(
                        MissionSession.status.in_(["finalized", "central_pending", "centralizing"]),
                    ).order_by(MissionSession.started_at.desc())
                )
                if local_mission is not None:
                    unresolved = db.scalar(
                        select(func.count(SyncConflict.id)).where(
                            SyncConflict.mission_uuid == local_mission.uuid,
                            SyncConflict.status == "pending",
                        )
                    ) or 0
                    local_mission.status = "centralized" if unresolved == 0 else "centralized_with_conflicts"
                    local_mission.centralized_at = self._now()
                    db.add(local_mission)
            self._finish_run(db, run, status="completed", cursor_end=next_central_sequence)
        except Exception as exc:  # noqa: BLE001
            sync_state.last_failed_sync_at = self._now()
            sync_state.last_error_code = "CENTRAL_PULL_APPLY_FAILED"
            sync_state.last_error_message = str(exc)
            sync_state.is_sync_running = False
            db.add(sync_state)
            db.commit()
            self._finish_run(db, run, status="failed", cursor_end=sync_state.last_pulled_sequence, error_code="CENTRAL_PULL_APPLY_FAILED", error_message=str(exc))
            raise
        db.refresh(sync_state)
        return sync_state

    def list_conflicts(self, db: Session) -> list[SyncConflict]:
        return db.scalars(select(SyncConflict).order_by(SyncConflict.created_at.desc())).all()

    def get_conflict(self, db: Session, conflict_uuid: py_uuid.UUID) -> SyncConflict:
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict_uuid))
        if conflict is None:
            raise NotFoundException("Conflict not found")
        return conflict

    def resolve_conflict(self, db: Session, conflict_uuid: py_uuid.UUID, *, resolution_type: str, resolved_payload: dict[str, Any] | None, current_user: User, resolution_reason: str | None = None) -> SyncConflict:
        if resolution_type == "keep_local":
            permission_service.require_permission(current_user, "sync.resolve_conflicts")
        else:
            suspend_for_data_safety("central_conflict_resolution")
        conflict = self.get_conflict(db, conflict_uuid)
        if resolution_type == "keep_local" and conflict.entity_type == "medical_visits":
            if (getattr(current_user, "role", "") or "").strip().lower() != "doctor":
                raise ForbiddenException("PHYSICIAN_REVIEW_REQUIRES_AUTHORIZED_VALIDATOR")
        if conflict.status == "resolved" and conflict.resolution_type == "keep_local":
            saved_reason = (conflict.resolved_payload or {}).get("resolution_reason")
            if resolution_reason is not None and saved_reason != resolution_reason:
                raise ConflictException("RESOLUTION_IDENTITY_REUSED_WITH_DIFFERENT_CONTENT")
            return conflict
        if conflict.status not in {"pending", "physician_review"}:
            raise ConflictException("Conflict is not pending.")
        entity = self._current_entity(db, conflict.entity_type, conflict.entity_uuid)
        if entity is None:
            raise NotFoundException("Conflicting entity no longer exists")
        if resolution_type == "keep_local" and conflict.entity_type == "medical_visits":
            entity = db.scalar(select(type(entity)).where(type(entity).uuid == conflict.entity_uuid).with_for_update())
        payload = resolved_payload or (conflict.mission_snapshot if resolution_type != "keep_central" else conflict.central_snapshot)
        if resolution_type == "keep_local":
            observed_raw = getattr(entity, "version", None)
            if observed_raw is None:
                observed_raw = getattr(entity, "sync_version", None)
            if observed_raw is None or conflict.central_version is None or int(observed_raw) != int(conflict.central_version):
                raise ConflictException("CONFLICT_VERSION_CHANGED")
            conflict.status = "resolved"
            conflict.resolution_type = "keep_local"
            conflict.resolved_payload = {"snapshot": dict(conflict.central_snapshot or {}), "resolution_reason": resolution_reason or ""}
            conflict.resolved_by_user_uuid = getattr(current_user, "uuid", None)
            conflict.resolved_at = self._now()
            db.add(conflict)
            db.add(AuditLog(user_id=current_user.id, actor_user_id=current_user.id,
                            action="central_conflict_resolution", entity_type="sync_conflicts",
                            entity_id=conflict.id, details_json={"resolution_type":"keep_local",
                            "conflict_uuid":str(conflict.uuid), "resolution_reason":resolution_reason,
                            "base_version":conflict.base_version, "central_version":conflict.central_version}))
            if db.info.get("inject_keep_local_failure"):
                raise RuntimeError("INJECTED_KEEP_LOCAL_FAILURE_BEFORE_COMMIT")
            db.commit()
            db.refresh(conflict)
            return conflict
        state = self.get_or_create_server_state(db, activate=True)
        with db.begin_nested():
            if resolution_type in {"accept_mission", "manual_merge", "create_revision"}:
                values = self._apply_values(db, type(entity), payload)
                for key, value in values.items():
                    setattr(entity, key, value)
            if isinstance(entity, SyncMetadataMixin):
                entity.sync_version = max(int(entity.sync_version or 1) + 1, int(conflict.central_version or 1) + 1)
                entity.central_version = entity.sync_version
                entity.central_server_uuid = state.server_uuid
                entity.central_finalized_at = self._now()
                entity.central_sync_status = "central_finalized"
                entity.central_sequence = self._next_central_sequence(db, state)
            db.add(entity)
            self._write_central_change(
                db,
                change_uuid=py_uuid.uuid4(),
                mission_uuid=conflict.mission_uuid or py_uuid.uuid4(),
                mission_sequence=conflict.mission_sequence,
                entity_type=conflict.entity_type,
                entity_uuid=conflict.entity_uuid,
                operation="update",
                base_version=conflict.central_version,
                entity_version=int(getattr(entity, "sync_version", conflict.central_version or 1)),
                changed_fields=sorted((payload or {}).keys()),
                payload=serialize_sync_payload(entity),
                source_device_uuid=conflict.source_device_uuid,
                source_user_uuid=getattr(current_user, "uuid", None),
                central_server_uuid=state.server_uuid,
                central_sequence=int(getattr(entity, "central_sequence", 0) or 0),
            )
            conflict.status = "resolved"
            conflict.resolution_type = resolution_type
            conflict.resolved_payload = payload
            conflict.resolved_by_user_uuid = getattr(current_user, "uuid", None)
            conflict.resolved_at = self._now()
            db.add(conflict)
        create_audit_log(
            db,
            current_user.id,
            "central_conflict_resolution",
            "sync_conflicts",
            conflict.id,
            details={"resolution_type": resolution_type, "conflict_uuid": str(conflict.uuid)},
        )
        db.refresh(conflict)
        return conflict

    def accept_incoming(self, db: Session, conflict_uuid: py_uuid.UUID, *, current_user: User,
                        operation_uuid: py_uuid.UUID, resolution_reason: str,
                        reconciliation_result: dict[str, Any] | None = None) -> SyncConflictDecision:
        """Test-only protected acceptance for a non-validated MedicalVisit."""
        if not resolution_reason or not resolution_reason.strip():
            raise BadRequestException("RESOLUTION_REASON_REQUIRED")
        verified_evidence = reconciliation_result or db.info.pop("verified_reconciliation", None)
        if not verified_evidence or verified_evidence.get("status") != "accepted_test_only":
            raise ForbiddenException("FRESH_EVIDENCE_REQUIRED")
        permission_service.require_permission(current_user, "sync.resolve_conflicts")
        if (getattr(current_user, "role", "") or "").strip().lower() != "doctor":
            raise ForbiddenException("PHYSICIAN_REVIEW_REQUIRES_AUTHORIZED_VALIDATOR")
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict_uuid).with_for_update())
        if conflict is None:
            raise NotFoundException("Conflict not found")
        existing = db.scalar(select(SyncConflictDecision).where(SyncConflictDecision.operation_uuid == operation_uuid))
        if existing:
            if existing.conflict_uuid != conflict.uuid or existing.reason != resolution_reason:
                raise ConflictException("DECISION_IDENTITY_REUSED_WITH_DIFFERENT_CONTENT")
            return existing
        if conflict.entity_type != "medical_visits" or conflict.status != "physician_review":
            raise ConflictException("CONFLICT_NOT_ACCEPTABLE")
        # Inbox/transport events are the durable source for received changes;
        # a local SyncChange row is not required for an incoming event.
        event = db.scalar(select(SyncChange).where(SyncChange.change_uuid == conflict.incoming_change_uuid))
        if event is None:
            event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == conflict.incoming_change_uuid))
        if event is None:
            raise NotFoundException("INCOMING_EVENT_NOT_FOUND")
        event_uuid = getattr(event, "change_uuid", None) or event.event_uuid
        details = verified_evidence.get("verification") or {}
        auth_ref = details.get("authorization") or {}
        if (verified_evidence.get("input_fingerprint") is None
                or auth_ref.get("evidence_uuid") is None
                or auth_ref.get("event_uuid") != str(event_uuid)):
            raise ConflictException("EVIDENCE_BINDING_INVALID")
        auth_record = db.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.event_uuid == event_uuid))
        delegation_ref = (auth_record.envelope or {}).get("authorization_reference") if auth_record else None
        if delegation_ref:
            from app.models.proof_trust import ProofDelegation
            delegation = db.scalar(select(ProofDelegation).where(
                ProofDelegation.delegation_uuid == py_uuid.UUID(str(delegation_ref))
            ).execution_options(populate_existing=True).with_for_update())
            if delegation is None or delegation.state != "active":
                raise ConflictException("DELEGATION_REVOKED")
        else:
            # Authorization envelopes bind the subject and clinic even when
            # they do not carry the delegation UUID. Resolve that trusted
            # scope locally and reject a revoked matching delegation.
            from app.models.proof_trust import ProofDelegation
            subject = (auth_record.envelope or {}).get("subject_user_uuid") if auth_record else None
            clinic = (auth_record.envelope or {}).get("clinic_uuid") if auth_record else None
            if subject and clinic:
                matches = db.scalars(select(ProofDelegation).where(ProofDelegation.entity_type == event.entity_type, ProofDelegation.operation == event.operation, ProofDelegation.user_uuid == py_uuid.UUID(str(subject)), ProofDelegation.clinic_uuid == py_uuid.UUID(str(clinic))).execution_options(populate_existing=True).with_for_update()).all()
                if matches and any(d.state != "active" for d in matches):
                    raise ConflictException("DELEGATION_REVOKED")
        entity = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid).with_for_update())
        if entity is None or entity.status == "validated" or entity.validated_at is not None:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        local_revision = db.scalar(select(LocalRevision).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == entity.uuid).order_by(LocalRevision.local_version.desc()).with_for_update())
        if local_revision is None or conflict.central_version != local_revision.local_version:
            raise ConflictException("CONFLICT_VERSION_CHANGED")
        incoming_snapshot = dict(conflict.mission_snapshot or {})
        if dict(getattr(event, "payload", {}) or {}) != incoming_snapshot:
            raise ConflictException("INCOMING_SNAPSHOT_MISMATCH")
        local_snapshot = dict(conflict.central_snapshot or {})
        decision_revision_uuid = py_uuid.uuid4()
        now = self._now()
        previous_contract = db.info.get("stage3_write_contract")
        previous_operation = db.info.get("local_operation_uuid")
        previous_apply = db.info.get("sync_apply_mode")
        db.info["stage3_write_contract"] = True
        db.info["local_operation_uuid"] = operation_uuid
        db.info["sync_apply_mode"] = True
        db.add(LocalWriteOperation(operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
                                   request_hash=hashlib.sha256((str(conflict.uuid) + resolution_reason).encode()).hexdigest(),
                                   entity_type="medical_visits", entity_uuid=entity.uuid,
                                   result_payload={}, created_at=now))
        db.flush()
        # Deterministic recovery-test hook: the caller owns rollback.
        # It is deliberately session-local and never exposed through an API.
        if db.info.pop("inject_accept_incoming_failure", False):
            if previous_contract is None: db.info.pop("stage3_write_contract", None)
            else: db.info["stage3_write_contract"] = previous_contract
            if previous_operation is None: db.info.pop("local_operation_uuid", None)
            else: db.info["local_operation_uuid"] = previous_operation
            if previous_apply is None: db.info.pop("sync_apply_mode", None)
            else: db.info["sync_apply_mode"] = previous_apply
            raise RuntimeError("INJECTED_ACCEPT_INCOMING_FAILURE_AFTER_FLUSH")
        for field in ("visit_date", "site_name", "form_data", "doctor_notes"):
            if field in incoming_snapshot:
                setattr(entity, field, incoming_snapshot[field])
        entity.version = int(local_revision.local_version) + 1
        entity.sync_version = entity.version
        db.add(entity)
        db.add(LocalRevision(revision_uuid=decision_revision_uuid, entity_type="medical_visits", entity_uuid=entity.uuid,
                             parent_revision_uuid=local_revision.revision_uuid, local_version=entity.version,
                             kind="conflict_accept", operation_uuid=operation_uuid, created_at=now))
        def digest(value: dict) -> str:
            return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        decision = SyncConflictDecision(decision_uuid=py_uuid.uuid4(), operation_uuid=operation_uuid,
            conflict_uuid=conflict.uuid, incoming_event_uuid=event_uuid,
            incoming_revision_uuid=event.revision_uuid, local_parent_revision_uuid=local_revision.revision_uuid,
            decision_revision_uuid=decision_revision_uuid, local_version=local_revision.local_version,
            incoming_version=int(getattr(event, "entity_version", conflict.base_version + 1 if conflict.base_version is not None else local_revision.local_version + 1)), local_snapshot=local_snapshot,
            incoming_snapshot=incoming_snapshot, local_snapshot_sha256=digest(local_snapshot),
            incoming_snapshot_sha256=digest(incoming_snapshot), reviewer_user_uuid=current_user.uuid,
            reason=resolution_reason, evidence_refs=verified_evidence, policy_version=details.get("checkpoint", {}).get("policy_version"), trust_reference=auth_ref.get("trust_reference"), created_at=now)
        db.add(decision)
        conflict.status = "resolved"; conflict.resolution_type = "accept_incoming"
        conflict.resolved_payload = {"decision_uuid": str(decision.decision_uuid), "resolution_reason": resolution_reason}
        conflict.resolved_by_user_uuid = current_user.uuid; conflict.resolved_at = now
        db.add(conflict)
        db.add(AuditLog(user_id=current_user.id, actor_user_id=current_user.id, action="central_conflict_accept_incoming",
                        entity_type="sync_conflicts", entity_id=conflict.id,
                        details_json={"decision_uuid": str(decision.decision_uuid), "reason": resolution_reason}))
        try:
            db.commit(); db.refresh(decision)
            return decision
        finally:
            if previous_contract is None: db.info.pop("stage3_write_contract", None)
            else: db.info["stage3_write_contract"] = previous_contract
            if previous_operation is None: db.info.pop("local_operation_uuid", None)
            else: db.info["local_operation_uuid"] = previous_operation
            if previous_apply is None: db.info.pop("sync_apply_mode", None)
            else: db.info["sync_apply_mode"] = previous_apply

    def bootstrap_request(self, db: Session, *, device_uuid: py_uuid.UUID, allow_overwrite_without_unsent_work: bool = False) -> CentralBootstrap:
        local_pending = db.scalar(
            select(func.count(SyncChange.id)).where(
                SyncChange.source_device_uuid == device_uuid,
                SyncChange.central_status.in_(["never_submitted", "central_pending"]),
            )
        ) or 0
        if local_pending and not allow_overwrite_without_unsent_work:
            raise ConflictException("BOOTSTRAP_UNSENT_LOCAL_WORK")
        state = self.get_or_create_server_state(db, activate=True)
        entity_counts = {
            entity: int(db.scalar(select(func.count(config.model.id))) or 0)
            for entity, config in SYNC_ENTITY_REGISTRY.items()
        }
        payload = {
            entity: [
                serialize_sync_payload(item)
                for item in db.scalars(select(config.model).order_by(config.model.id.asc())).all()
            ]
            for entity, config in SYNC_ENTITY_REGISTRY.items()
        }
        manifest = {
            "central_server_uuid": str(state.server_uuid),
            "central_generation_uuid": str(state.server_generation_uuid),
            "snapshot_central_sequence": int(state.current_central_sequence or 0),
            "schema_revision": state.schema_revision,
            "protocol_version": state.protocol_version,
            "creation_time": self._now().isoformat(),
            "entity_counts": entity_counts,
            "file_metadata": {},
        }
        checksum = hashlib.sha256(json.dumps({"manifest": manifest, "payload": payload}, sort_keys=True).encode("utf-8")).hexdigest()
        bootstrap = CentralBootstrap(
            device_uuid=device_uuid,
            central_server_uuid=state.server_uuid,
            central_generation_uuid=state.server_generation_uuid,
            snapshot_central_sequence=int(state.current_central_sequence or 0),
            schema_revision=state.schema_revision,
            protocol_version=state.protocol_version,
            checksum=checksum,
            manifest=manifest,
            payload=payload,
        )
        db.add(bootstrap)
        db.commit()
        db.refresh(bootstrap)
        return bootstrap

    def bootstrap_manifest(self, db: Session, bootstrap_uuid: py_uuid.UUID) -> CentralBootstrap:
        bootstrap = db.scalar(select(CentralBootstrap).where(CentralBootstrap.bootstrap_uuid == bootstrap_uuid))
        if bootstrap is None:
            raise NotFoundException("Bootstrap request not found")
        return bootstrap

    def bootstrap_complete(self, db: Session, bootstrap_uuid: py_uuid.UUID, *, applied_locally: bool, notes: str | None = None) -> CentralBootstrap:
        bootstrap = self.bootstrap_manifest(db, bootstrap_uuid)
        bootstrap.applied_locally = applied_locally
        bootstrap.completed_at = self._now()
        bootstrap.status = "completed"
        bootstrap.notes = notes
        db.add(bootstrap)
        db.commit()
        db.refresh(bootstrap)
        return bootstrap

    def data_integrity(self, db: Session) -> dict[str, Any]:
        null_uuid_issues: list[str] = []
        duplicate_uuid_issues: list[str] = []
        broken_uuid_relationships: list[str] = []
        duplicate_change_uuid_issues: list[str] = []
        invalid_cursor_issues: list[str] = []

        for entity_type, config in SYNC_ENTITY_REGISTRY.items():
            model = config.model
            uuid_col = getattr(model, "uuid", None)
            if uuid_col is None:
                continue
            nulls = db.scalar(select(func.count(model.id)).where(model.uuid.is_(None))) or 0
            if nulls:
                null_uuid_issues.append(f"{entity_type}:{nulls}")
            duplicates = db.execute(
                select(model.uuid, func.count(model.id))
                .group_by(model.uuid)
                .having(func.count(model.id) > 1)
            ).all()
            if duplicates:
                duplicate_uuid_issues.append(f"{entity_type}:{len(duplicates)}")
            mapper = inspect(model)
            for relationship in mapper.relationships:
                payload_key = f"{relationship.key}_uuid"
                if hasattr(model, payload_key):
                    target_model = relationship.mapper.class_
                    rows = db.scalars(select(model).where(getattr(model, payload_key).is_not(None))).all()
                    for row in rows:
                        target_uuid = getattr(row, payload_key, None)
                        if target_uuid and db.scalar(select(target_model.id).where(target_model.uuid == target_uuid)) is None:
                            broken_uuid_relationships.append(f"{entity_type}:{payload_key}:{row.id}")

        duplicate_changes = db.execute(
            select(SyncChange.change_uuid, func.count(SyncChange.id))
            .group_by(SyncChange.change_uuid)
            .having(func.count(SyncChange.id) > 1)
        ).all()
        if duplicate_changes:
            duplicate_change_uuid_issues.append(str(len(duplicate_changes)))

        for state in db.scalars(select(DeviceSyncState)).all():
            if int(state.last_pulled_sequence or 0) > int(state.last_pushed_sequence or state.final_mission_sequence or 0):
                invalid_cursor_issues.append(str(state.id))

        return {
            "null_uuid_issues": null_uuid_issues,
            "duplicate_uuid_issues": duplicate_uuid_issues,
            "broken_uuid_relationships": broken_uuid_relationships,
            "duplicate_change_uuid_issues": duplicate_change_uuid_issues,
            "invalid_cursor_issues": invalid_cursor_issues,
            "sync_version_issues": [],
            "missing_device_identity": self._local_device(db).uuid is None,
            "orphaned_mission_session": [],
            "missing_mission_sequence": [],
            "missing_central_sequence_for_finalized_changes": [],
            "orphaned_medical_visits": [],
            "orphaned_certificates": [],
            "missing_signature_file_metadata": [],
            "invalid_central_generation_reference": [],
        }


central_sync_service = CentralSyncService()
