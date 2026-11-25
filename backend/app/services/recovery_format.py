"""Pure, non-applying interpretation of captured legacy bytes.

No patient content is emitted in errors or summaries.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

MAX_CAPTURE_BYTES = 16 * 1024 * 1024
FORMAT_VERSION = 1
KINDS = {"browser_local_storage", "legacy_package", "postgres_journal"}
JOURNAL_TABLES = {"sync_changes", "client_sync_changes", "client_local_sync_runs", "client_local_sync_state", "device_sync_states", "sync_conflicts"}
SENSITIVE_KEYS = {"password", "password_hash", "refresh_token", "access_token", "token", "secret", "credential", "authorization", "signature_png", "workspace_password_hash"}
BROWSER_CONTEXT_KEYS = {"clinic_sync_meta", "clinic_mission_manifest_cache", "clinic_central_sync_runs", "clinic_central_sync_cursor"}
BROWSER_CONTEXT_PREFIXES = ("medical_visit_pending_operation:",)


def _browser_context_key(key: str) -> bool:
    return key in BROWSER_CONTEXT_KEYS or key.startswith(BROWSER_CONTEXT_PREFIXES)


class CaptureValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedItem:
    ordinal: int
    source_ref: str
    raw_fragment: str
    entity_type: str | None
    legacy_id: str | None
    entity_uuid: uuid.UUID | None
    state: str
    reason_code: str | None


@dataclass(frozen=True)
class ParsedCapture:
    items: tuple[ParsedItem, ...]
    reason_code: str | None = None


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_envelope(kind: str, version: int, raw: str, expected_sha256: str) -> int:
    if kind not in KINDS or version != FORMAT_VERSION:
        raise CaptureValidationError("RECOVERY_FORMAT_UNSUPPORTED")
    byte_length = len(raw.encode("utf-8"))
    if byte_length == 0 or byte_length > MAX_CAPTURE_BYTES:
        raise CaptureValidationError("RECOVERY_CAPTURE_SIZE_INVALID")
    if digest(raw) != expected_sha256.lower():
        raise CaptureValidationError("RECOVERY_CHECKSUM_MISMATCH")
    return byte_length


def _has_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_KEYS or normalized.endswith("_token") or normalized.endswith("_secret"):
                return True
            if _has_sensitive_key(child):
                return True
    elif isinstance(value, list):
        return any(_has_sensitive_key(child) for child in value)
    return False


def _identity(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError, AttributeError):
        return None


def _record(ordinal: int, ref: str, raw: str, data: Any, entity: str | None, source_identity: str | None, *, draft: bool = False) -> ParsedItem:
    entry = data if isinstance(data, dict) else {}
    entity_uuid = _identity(entry.get("uuid") or entry.get("entity_uuid"))
    legacy = entry.get("id") or entry.get("entity_id")
    legacy_id = str(legacy) if isinstance(legacy, (str, int)) and not isinstance(legacy, bool) else None
    numerical_relations = [key for key, value in entry.items()
                           if key.endswith("_id") and isinstance(value, int) and not isinstance(value, bool)
                           and key not in {"id", "entity_id"} and not entry.get(f"{key[:-3]}_uuid")]
    reason = ("DRAFT_NOT_COMMITTED" if draft else
              "SOURCE_IDENTITY_MISSING" if not source_identity else
              "LEGACY_NUMERIC_RELATION" if numerical_relations else
              "IDENTITY_AMBIGUOUS" if not entity_uuid else None)
    if not isinstance(data, dict):
        reason = "ITEM_MALFORMED"
    return ParsedItem(ordinal, ref, raw, entity, legacy_id, entity_uuid,
                      "needs_review" if reason else "waiting_engine", reason)


def interpret(kind: str, raw: str, source_identity: str | None) -> ParsedCapture:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return ParsedCapture((), "SOURCE_JSON_MALFORMED")
    if _has_sensitive_key(data):
        raise CaptureValidationError("RECOVERY_SENSITIVE_FIELD_REJECTED")
    if kind == "browser_local_storage":
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, dict) or any(not isinstance(key, str) or not isinstance(value, str) or
                                                 (key != "clinic_sync_queue" and not _browser_context_key(key) and
                                                  not key.startswith("medical-folder.worker-medical-file."))
                                                 for key, value in entries.items()):
            raise CaptureValidationError("RECOVERY_BROWSER_KEYS_INVALID")
        result: list[ParsedItem] = []
        for key in sorted(entries):
            original = entries[key]
            try:
                value = json.loads(original)
            except ValueError:
                if _browser_context_key(key):
                    continue  # Original malformed context is still preserved in the source.
                result.append(ParsedItem(len(result), key, original, None, None, None, "needs_review", "ITEM_JSON_MALFORMED"))
                continue
            if _has_sensitive_key(value):
                raise CaptureValidationError("RECOVERY_SENSITIVE_FIELD_REJECTED")
            if _browser_context_key(key):
                continue  # Cursor/manifests are context, never medical write operations.
            if key == "clinic_sync_queue":
                if not isinstance(value, dict):
                    result.append(ParsedItem(len(result), key, original, None, None, None, "needs_review", "QUEUE_MALFORMED"))
                    continue
                for entity in sorted(value):
                    rows = value[entity]
                    if not isinstance(rows, list):
                        result.append(ParsedItem(len(result), f"{key}/{entity}", json.dumps(rows, ensure_ascii=False), entity, None, None, "needs_review", "QUEUE_MALFORMED"))
                        continue
                    for index, row in enumerate(rows):
                        ref = f"{key}/{entity}/{index}"
                        result.append(_record(len(result), ref, json.dumps(row, ensure_ascii=False), row, entity, source_identity))
            else:
                result.append(_record(len(result), key, original, value, "medical_draft", source_identity, draft=True))
        return ParsedCapture(tuple(result))
    if kind == "legacy_package":
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
            return ParsedCapture((), "PACKAGE_MALFORMED")
        if not isinstance(data.get("tombstones", []), list):
            return ParsedCapture((), "PACKAGE_MALFORMED")
        declared = data.get("checksum_sha256")
        if declared:
            payload = {key: value for key, value in data.items() if key != "checksum_sha256"}
            check = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
            if check != declared:
                raise CaptureValidationError("RECOVERY_PACKAGE_CHECKSUM_MISMATCH")
        result = []
        for entity in sorted(data["data"]):
            rows = data["data"][entity]
            if not isinstance(rows, list):
                return ParsedCapture((), "PACKAGE_MALFORMED")
            for index, row in enumerate(rows):
                result.append(_record(len(result), f"data/{entity}/{index}", json.dumps(row, ensure_ascii=False), row, entity, source_identity))
        for index, row in enumerate(data.get("tombstones") or []):
            result.append(ParsedItem(len(result), f"tombstones/{index}", json.dumps(row, ensure_ascii=False), None, None, None, "needs_review", "TOMBSTONE_REVIEW"))
        return ParsedCapture(tuple(result))
    if kind == "postgres_journal":
        if not isinstance(data, dict) or data.get("table") not in JOURNAL_TABLES or not isinstance(data.get("rows"), list):
            raise CaptureValidationError("RECOVERY_JOURNAL_FORMAT_INVALID")
        result = []
        for index, row in enumerate(data["rows"]):
            ref = f"{data['table']}/{row.get('id', index) if isinstance(row, dict) else index}"
            result.append(_record(index, ref, json.dumps(row, ensure_ascii=False), row, data["table"], source_identity))
        return ParsedCapture(tuple(result))
    raise CaptureValidationError("RECOVERY_FORMAT_UNSUPPORTED")
