from __future__ import annotations

from datetime import date, datetime
import uuid as py_uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.utils.json_serializer import make_json_serializable


def _normalize_audit_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return make_json_serializable(value)


def build_update_details(entity, changes: dict) -> dict:
    details: dict = {}
    for key, new_value in changes.items():
        old_value = getattr(entity, key, None)
        old_normalized = _normalize_audit_value(old_value)
        new_normalized = _normalize_audit_value(new_value)
        if old_normalized == new_normalized:
            continue
        details[key] = {
            "from": old_normalized,
            "to": new_normalized,
        }
    return details


def create_audit_log(
    db: Session,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    metadata: dict | None = None,
    user_agent: str | None = None,
    worker_id: int | None = None,
    device_uuid: py_uuid.UUID | str | None = None,
) -> AuditLog:
    resolved_device_uuid = device_uuid or db.info.get("sync_source_device_uuid")
    if isinstance(resolved_device_uuid, str):
        try:
            resolved_device_uuid = py_uuid.UUID(resolved_device_uuid)
        except ValueError:
            resolved_device_uuid = None
    audit = AuditLog(
        user_id=user_id,
        actor_user_id=actor_user_id or user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        target_user_id=target_user_id,
        worker_id=worker_id,
        device_uuid=resolved_device_uuid,
        ip_address=ip_address,
        details_json=make_json_serializable(details or {}),
        old_values=make_json_serializable(old_values or {}),
        new_values=make_json_serializable(new_values or {}),
        metadata_json=make_json_serializable(metadata or {}),
        user_agent=user_agent,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
