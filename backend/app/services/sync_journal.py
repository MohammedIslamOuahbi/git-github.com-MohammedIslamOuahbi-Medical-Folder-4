from __future__ import annotations

import uuid as py_uuid
import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.orm.attributes import NO_VALUE
from sqlalchemy.orm import Session

from app.database import SyncMetadataMixin
from app.models.mission_session import MissionSession
from app.models.runtime_config import RuntimeConfig
from app.models.sync_change import SyncChange
from app.models.local_revision import LocalRevision
from app.exceptions import ConflictException
from app.sync.registry import SYNC_ENTITY_REGISTRY

SECRET_FIELDS = {"password_hash", "signature_png", "refresh_token", "access_token", "token", "secret"}

_REGISTERED = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_syncable_instance(instance: object) -> bool:
    return any(isinstance(instance, config.model) for config in SYNC_ENTITY_REGISTRY.values())


def _entity_type_for(instance: object) -> str | None:
    for entity_type, config in SYNC_ENTITY_REGISTRY.items():
        if isinstance(instance, config.model):
            return entity_type
    return None


def _normalize_value(value: Any) -> Any:
    if isinstance(value, py_uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value


def _relationship_uuid_payload(instance: object) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    instance_state = inspect(instance)
    mapper = instance_state.mapper
    for relationship in mapper.relationships:
        key = relationship.key
        if relationship.uselist:
            continue
        attribute_state = instance_state.attrs[key]
        value = attribute_state.loaded_value
        if value is not NO_VALUE and value is not None:
            relation_uuid = getattr(value, "uuid", None)
            if relation_uuid is not None:
                payload[f"{key}_uuid"] = str(relation_uuid)
                continue
        local_columns = list(relationship.local_columns)
        if len(local_columns) != 1:
            continue
        local_column = local_columns[0]
        if not local_column.key.endswith("_id"):
            continue
        local_id = getattr(instance, local_column.key, None)
        if local_id is None:
            continue
        related_mapper = relationship.mapper
        related_model = related_mapper.class_
        related_pk = list(related_mapper.primary_key)
        if len(related_pk) != 1 or not hasattr(related_model, "uuid"):
            continue
        related_uuid = None
        if instance_state.session is not None:
            related_uuid = instance_state.session.execute(
                select(getattr(related_model, "uuid")).where(related_pk[0] == local_id)
            ).scalar_one_or_none()
        if related_uuid is not None:
            payload[f"{key}_uuid"] = str(related_uuid)
    return payload


def serialize_sync_payload(instance: object) -> dict[str, Any]:
    mapper = inspect(type(instance))
    payload: dict[str, Any] = {}
    for column in mapper.columns:
        key = column.key
        if key in SECRET_FIELDS:
            continue
        if key == "id" or key.endswith("_id"):
            continue
        payload[key] = _normalize_value(getattr(instance, key))
    payload.update(_relationship_uuid_payload(instance))
    return payload


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _changed_fields(instance: object, operation: str) -> list[str] | None:
    if operation == "insert":
        return sorted(serialize_sync_payload(instance).keys())
    state = inspect(instance)
    fields: list[str] = []
    for attr in state.attrs:
        if attr.key in SECRET_FIELDS or attr.key == "id" or attr.key.endswith("_id"):
            continue
        if attr.history.has_changes():
            fields.append(attr.key)
    fields.extend(key for key in _relationship_uuid_payload(instance) if key not in fields)
    return sorted(fields) or None


def _operation_for(instance: object, deleted: bool = False) -> str:
    if deleted:
        return "delete"
    state = inspect(instance)
    if "deleted_at" in state.attrs and getattr(instance, "deleted_at", None):
        deleted_attr = state.attrs.deleted_at
        if deleted_attr.history.has_changes():
            return "delete"
    return "update"


def _next_mission_sequence(session: Session, mission_session_uuid: py_uuid.UUID | None) -> int | None:
    if mission_session_uuid is None:
        return None
    mission = session.scalar(select(MissionSession).where(MissionSession.uuid == mission_session_uuid))
    if mission is None:
        return None
    mission.mission_current_sequence = int(mission.mission_current_sequence or 0) + 1
    return mission.mission_current_sequence


def register_sync_journal() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    @event.listens_for(Session, "before_flush")
    def _sync_before_flush(session: Session, _flush_context, _instances) -> None:
        if session.info.get("sync_apply_mode") or session.info.get("sync_bootstrap_mode"):
            return
        runtime = session.get(RuntimeConfig, 1)
        if runtime is not None and runtime.runtime_mode == "mission_client":
            has_business_write = any(
                _is_syncable_instance(instance)
                for group in (session.new, session.dirty, session.deleted)
                for instance in group
            )
            if has_business_write:
                raise ConflictException("LOCAL_BUSINESS_WRITES_DISABLED_IN_MISSION_CLIENT_MODE")
        current_device_uuid = session.info.get("sync_source_device_uuid")
        current_mission_uuid = session.info.get("sync_mission_session_uuid")
        for collection in (session.new, session.dirty):
            for instance in collection:
                if not _is_syncable_instance(instance):
                    continue
                if not isinstance(instance, SyncMetadataMixin):
                    continue
                if getattr(instance, "origin_device_uuid", None) is None and current_device_uuid is not None:
                    instance.origin_device_uuid = current_device_uuid
                if getattr(instance, "last_modified_device_uuid", None) != current_device_uuid:
                    instance.last_modified_device_uuid = current_device_uuid
                if getattr(instance, "origin_mission_session_uuid", None) is None and current_mission_uuid is not None:
                    instance.origin_mission_session_uuid = current_mission_uuid
                if current_mission_uuid is not None:
                    instance.last_modified_mission_session_uuid = current_mission_uuid
                if instance in session.dirty and session.is_modified(instance, include_collections=False):
                    instance.sync_version = max(1, int(getattr(instance, "sync_version", 1) or 1) + 1)
                    if hasattr(instance, "version"):
                        instance.version = max(1, int(getattr(instance, "version", 1) or 1) + 1)
                if hasattr(instance, "sync_status"):
                    instance.sync_status = "pending_sync"
                instance.central_sync_status = "central_pending"

    @event.listens_for(Session, "after_flush")
    def _sync_after_flush(session: Session, _flush_context) -> None:
        if session.info.get("sync_apply_mode") or session.info.get("sync_bootstrap_mode"):
            return
        pending_changes = []
        mission_session_uuid = session.info.get("sync_mission_session_uuid")
        mission_server_uuid = session.info.get("sync_mission_server_uuid")
        source_device_uuid = session.info.get("sync_source_device_uuid")
        source_user_uuid = session.info.get("sync_source_user_uuid")
        source_generation_uuid = session.info.get("sync_source_generation_uuid")
        source_clinic_uuid = session.info.get("sync_source_clinic_uuid")

        for instance in session.new:
            if _is_syncable_instance(instance) and getattr(instance, "uuid", None) is not None:
                pending_changes.append((instance, "insert"))
        for instance in session.dirty:
            if _is_syncable_instance(instance) and session.is_modified(instance, include_collections=False):
                pending_changes.append((instance, _operation_for(instance)))
        for instance in session.deleted:
            if _is_syncable_instance(instance) and getattr(instance, "uuid", None) is not None:
                pending_changes.append((instance, "delete"))

        for instance, operation in pending_changes:
            entity_type = _entity_type_for(instance)
            entity_uuid = getattr(instance, "uuid", None)
            if entity_type is None or entity_uuid is None:
                continue
            entity_version = max(1, int(getattr(instance, "sync_version", 1) or 1))
            prior_row = session.connection().execute(
                select(LocalRevision.revision_uuid, LocalRevision.local_version).where(
                    LocalRevision.entity_type == entity_type, LocalRevision.entity_uuid == entity_uuid,
                ).order_by(LocalRevision.local_version.desc()).limit(1)
            ).one_or_none()
            prior_revision = prior_row.revision_uuid if prior_row else None
            if prior_row and entity_version <= prior_row.local_version:
                entity_version = prior_row.local_version + 1
            if prior_revision is None and operation != "insert":
                baseline_version = entity_version if operation == "delete" else max(1, entity_version - 1)
                prior_revision = py_uuid.uuid4()
                session.connection().execute(LocalRevision.__table__.insert().values(
                    revision_uuid=prior_revision, entity_type=entity_type, entity_uuid=entity_uuid,
                    local_version=baseline_version, kind="baseline", operation_uuid=None,
                    parent_revision_uuid=None, created_at=_now(),
                ))
                entity_version = max(entity_version, baseline_version + 1)
            revision_uuid = py_uuid.uuid4()
            session.connection().execute(LocalRevision.__table__.insert().values(
                revision_uuid=revision_uuid, entity_type=entity_type, entity_uuid=entity_uuid,
                parent_revision_uuid=prior_revision, local_version=entity_version,
                kind=operation, operation_uuid=session.info.get("local_operation_uuid"), created_at=_now(),
            ))
            mission_sequence = _next_mission_sequence(session, mission_session_uuid)
            event_payload = serialize_sync_payload(instance)
            event_payload["sync_version"] = entity_version
            content_sha256 = payload_sha256(event_payload)
            source_sequence = mission_sequence or entity_version
            session.connection().execute(
                SyncChange.__table__.insert(),
                [
                    {
                        "change_uuid": py_uuid.uuid4(),
                        "revision_uuid": revision_uuid,
                        "operation_uuid": session.info.get("local_operation_uuid"),
                        "schema_version": 1,
                        "content_sha256": content_sha256,
                        "source_generation_uuid": source_generation_uuid,
                        "source_sequence": source_sequence,
                        "source_clinic_uuid": source_clinic_uuid,
                        "entity_type": entity_type,
                        "entity_uuid": entity_uuid,
                        "operation": operation,
                        "base_version": entity_version - 1,
                        "entity_version": entity_version,
                        "changed_fields": _changed_fields(instance, operation),
                        "payload": event_payload,
                        "source_device_uuid": source_device_uuid,
                        "source_user_uuid": source_user_uuid,
                        "mission_session_uuid": mission_session_uuid,
                        "mission_server_uuid": mission_server_uuid,
                        "mission_sequence": mission_sequence,
                        "central_server_uuid": getattr(instance, "central_server_uuid", None),
                        "central_sequence": getattr(instance, "central_sequence", None),
                        "central_status": getattr(instance, "central_sync_status", "never_submitted"),
                        "occurred_at": _now(),
                        "mission_committed_at": _now() if mission_session_uuid is not None else None,
                        "retry_count": 0,
                    }
                ],
            )

    _REGISTERED = True


# Install the fail-closed guard when this module is imported by a service or the
# sidecar application. The function remains idempotent for app.main and tests.
register_sync_journal()
