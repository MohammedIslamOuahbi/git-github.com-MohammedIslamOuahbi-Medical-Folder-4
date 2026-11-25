from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.core.permissions import has_role
from app.exceptions import ForbiddenException
from app.models.user import User

SIGNATURE_AUTHORIZATION_MESSAGE = "Only authorized validators can sign medical documents."
ALLOWED_VALIDATOR_ROLES = {"super_admin", "super admin", "admin", "doctor"}
SIGNATURE_FLAG_KEYS = (
    "includeValidatorSignature",
    "includeDoctorSignature",
    "includeWorkspaceSignature",
    "includeUserSignature",
)
VALIDATOR_METADATA_KEYS = (
    "validatorId",
    "validatorName",
    "validatorRole",
    "validatedAt",
    "validatorSignatureImagePath",
)
_BOOLEAN_SIGNATURE_KEYS = {key.lower() for key in SIGNATURE_FLAG_KEYS}
_SIGNATURE_FIELD_KEYS = {
    key.lower()
    for key in (
        *SIGNATURE_FLAG_KEYS,
        *VALIDATOR_METADATA_KEYS,
        "doctorSignature",
        "validatorSignature",
        "validationDoctorSignature",
    )
}


def can_validate_documents(user: User | None) -> bool:
    return bool(user) and has_role(user, *ALLOWED_VALIDATOR_ROLES)


def require_document_validator(user: User | None) -> None:
    if can_validate_documents(user):
        return
    raise ForbiddenException(SIGNATURE_AUTHORIZATION_MESSAGE)


def can_sign_medical_documents(user: User | None) -> bool:
    return can_validate_documents(user)


def ensure_can_sign_medical_documents(user: User | None) -> None:
    require_document_validator(user)


def ensure_signature_payload_authorized(
    *,
    user: User | None,
    payload: Any,
    existing_payload: Any = None,
) -> None:
    if can_validate_documents(user):
        return

    incoming = _flatten_signature_values(payload)
    existing = _flatten_signature_values(existing_payload)

    for path, next_value in incoming.items():
        previous_value = existing.get(path)
        if next_value == previous_value:
            continue
        if _is_active_signature_value(next_value) or _is_active_signature_value(previous_value):
            raise ForbiddenException(SIGNATURE_AUTHORIZATION_MESSAGE)


def normalize_validator_signature_dict(
    payload: object,
    *,
    current_user: User | None = None,
    existing_payload: object | None = None,
) -> dict[str, Any]:
    snapshot = deepcopy(payload) if isinstance(payload, dict) else {}
    existing = deepcopy(existing_payload) if isinstance(existing_payload, dict) else {}

    requested_flag = _read_signature_flag(snapshot)
    existing_flag = _read_signature_flag(existing)
    include_validator_signature = requested_flag if requested_flag is not None else existing_flag

    for key in SIGNATURE_FLAG_KEYS:
        if key != "includeValidatorSignature":
            snapshot.pop(key, None)

    if include_validator_signature is None:
        include_validator_signature = False

    snapshot["includeValidatorSignature"] = bool(include_validator_signature)

    for key in VALIDATOR_METADATA_KEYS:
        if key not in snapshot and key in existing:
            snapshot[key] = existing.get(key)

    if snapshot["includeValidatorSignature"] and current_user and can_validate_documents(current_user):
        snapshot.update(build_validator_metadata(current_user))
    elif requested_flag is False:
        for key in VALIDATOR_METADATA_KEYS:
            snapshot.pop(key, None)

    return snapshot


def build_validator_metadata(user: User) -> dict[str, Any]:
    first_name = (getattr(user, "first_name", None) or "").strip()
    last_name = (getattr(user, "last_name", None) or "").strip()
    full_name = (getattr(user, "full_name", None) or "").strip()
    validator_name = full_name or " ".join(part for part in (first_name, last_name) if part).strip()
    validator_name = validator_name or (getattr(user, "email", None) or "").strip() or f"User {user.id}"
    validator_role = (getattr(user, "role", None) or "").strip()

    return {
        "validatorId": user.id,
        "validatorName": validator_name,
        "validatorRole": validator_role,
        "validatedAt": datetime.now(timezone.utc).isoformat(),
        "validatorSignatureImagePath": (getattr(user, "signature_path", None) or "").strip() or None,
    }


def get_validator_display_name(payload: Mapping[str, Any] | None, fallback: str = "") -> str:
    if not isinstance(payload, Mapping):
        return fallback
    for key in ("validatorName", "doctor_name", "doctorName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def get_validator_display_role(payload: Mapping[str, Any] | None, fallback: str = "") -> str:
    if not isinstance(payload, Mapping):
        return fallback
    for key in ("validatorRole", "doctorRole", "role"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _read_signature_flag(payload: Mapping[str, Any]) -> bool | None:
    for key in SIGNATURE_FLAG_KEYS:
        if key in payload and payload.get(key) is not None:
            return bool(payload.get(key))
    return None


def _flatten_signature_values(payload: Any, path: str = "") -> dict[str, Any]:
    values: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}" if path else str(key)
            if _is_signature_key(key):
                values[child_path] = _normalize_signature_value(key, value)
            if isinstance(value, (Mapping, list)):
                values.update(_flatten_signature_values(value, child_path))
        return values

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for index, item in enumerate(payload):
            child_path = f"{path}[{index}]"
            values.update(_flatten_signature_values(item, child_path))
    return values


def _is_signature_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.lower()
    return normalized in _SIGNATURE_FIELD_KEYS or "signature" in normalized


def _normalize_signature_value(key: str, value: Any) -> Any:
    normalized_key = key.lower()
    if normalized_key in _BOOLEAN_SIGNATURE_KEYS:
        return bool(value)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return value


def _is_active_signature_value(value: Any) -> bool:
    if value in (None, False, "", (), [], {}):
        return False
    return True
