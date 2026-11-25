from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

import hashlib
import json
import uuid as py_uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.client_sync_change import ClientSyncChange
from app.services.server_identity import API_VERSION, get_public_server_identity

CLIENT_SYNC_SCHEMA_VERSION = 1

SYNC_TABLES: tuple[dict[str, Any], ...] = (
    {"entity": "users", "table": "users", "exclude": {"password_hash", "local_id"}},
    {"entity": "permissions", "table": "permissions", "exclude": set()},
    {"entity": "user_permissions", "table": "user_permissions", "exclude": set()},
    {"entity": "companies", "table": "companies", "exclude": {"local_id"}},
    {"entity": "branches", "table": "branches", "exclude": {"local_id"}},
    {"entity": "drilling_sites", "table": "drilling_sites", "exclude": {"local_id"}},
    {"entity": "medical_tests", "table": "medical_tests", "exclude": set()},
    {"entity": "medical_campaigns", "table": "medical_campaigns", "exclude": {"local_id"}},
    {"entity": "campaign_workers", "table": "campaign_workers", "exclude": set()},
    {"entity": "campaign_tests", "table": "campaign_tests", "exclude": set()},
    {"entity": "doctor_campaigns", "table": "doctor_campaigns", "exclude": set()},
    {"entity": "assistant_campaigns", "table": "assistant_campaigns", "exclude": set()},
    {"entity": "workers", "table": "workers", "exclude": {"local_id"}},
    {"entity": "medical_visits", "table": "medical_visits", "exclude": set()},
    {"entity": "worker_tests", "table": "worker_tests", "exclude": set()},
    {"entity": "prescriptions", "table": "prescriptions", "exclude": set()},
    {"entity": "prescription_items", "table": "prescription_items", "exclude": set()},
    {"entity": "orientation_certificates", "table": "orientation_certificates", "exclude": set()},
    {"entity": "aptitude_certificates", "table": "aptitude_certificates", "exclude": set()},
    {"entity": "workspaces", "table": "workspaces", "exclude": {"workspace_password_hash", "local_id"}},
    {"entity": "import_jobs", "table": "import_jobs", "exclude": set()},
    {"entity": "import_rows", "table": "import_rows", "exclude": set()},
)

TABLE_ORDER = tuple(item["entity"] for item in SYNC_TABLES)
TABLE_BY_ENTITY = {str(item["entity"]): item for item in SYNC_TABLES}


def _is_uuid_like(value: str) -> bool:
    try:
        py_uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


class ClientSyncService:
    def __init__(self, tables: tuple[dict[str, Any], ...] = SYNC_TABLES) -> None:
        self.tables = tables

    def status(self, db: Session, after_cursor: int = 0) -> dict[str, Any]:
        self._validate_cursor(db, after_cursor)
        available = self._count_journal_changes(db, after_cursor)
        return {
            "application": "medical-folder",
            "server_id": get_public_server_identity()["server_id"],
            "schema_version": CLIENT_SYNC_SCHEMA_VERSION,
            "last_available_cursor": self._current_cursor(db),
            "available_update_count": sum(available.values()),
            "record_counts": available,
            "supported_entities": list(TABLE_ORDER),
            "mode": "SERVER_TO_CLIENT_ONLY",
        }

    def export(self, db: Session, after_cursor: int = 0, limit_per_entity: int = 1000) -> dict[str, Any]:
        suspend_for_data_safety("client_package_export")
        self._validate_cursor(db, after_cursor)
        from_cursor = max(after_cursor, 0)
        to_cursor = self._current_cursor(db)
        is_initial_sync = from_cursor == 0

        if is_initial_sync:
            data = self._full_snapshot(db, to_cursor, limit_per_entity)
            tombstones: list[dict[str, Any]] = []
        else:
            data, tombstones = self._incremental_changes(db, from_cursor, to_cursor, limit_per_entity)

        record_counts = {entity: len(rows) for entity, rows in data.items()}
        created_at = datetime.now(timezone.utc).isoformat()
        server_identity = get_public_server_identity()
        package_id = hashlib.sha256(
            f"{server_identity['server_id']}:{from_cursor}:{to_cursor}:{created_at}".encode("utf-8")
        ).hexdigest()[:24]
        payload = {
            "application": "medical-folder",
            "server_id": server_identity["server_id"],
            "server_identity": server_identity,
            "from_cursor": from_cursor,
            "to_cursor": to_cursor,
            "schema_version": CLIENT_SYNC_SCHEMA_VERSION,
            "is_initial_sync": is_initial_sync,
            "generated_at": created_at,
            "created_at": created_at,
            "package_id": package_id,
            "application_version": API_VERSION,
            "mode": "SERVER_TO_CLIENT_ONLY",
            "source_of_truth": "SERVER_POSTGRESQL",
            "target_model": "LOCAL_SYNCHRONIZED_COPY",
            "workspace": {
                "id": None,
                "name": "Global",
            },
            "record_counts": record_counts,
            "table_order": list(TABLE_ORDER),
            "tombstones": tombstones,
            "attachments": [],
            "data": data,
        }
        payload["checksum_sha256"] = self._checksum(payload)
        return payload

    def _validate_cursor(self, db: Session, after_cursor: int) -> None:
        if after_cursor < 0:
            raise ValueError("INVALID_SYNC_CURSOR")
        current = self._current_cursor(db)
        if after_cursor > current:
            raise ValueError("SYNC_CURSOR_AHEAD_OF_SERVER")

    def _current_cursor(self, db: Session) -> int:
        value = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM client_sync_changes")).scalar()
        return int(value or 0)

    def _count_journal_changes(self, db: Session, after_cursor: int) -> dict[str, int]:
        counts = {entity: 0 for entity in TABLE_ORDER}
        rows = db.execute(
            text(
                """
                SELECT entity_type, COUNT(*) AS count
                FROM client_sync_changes
                WHERE id > :after_cursor
                GROUP BY entity_type
                """
            ),
            {"after_cursor": after_cursor},
        ).mappings()
        for row in rows:
            entity = str(row["entity_type"])
            if entity in counts:
                counts[entity] = int(row["count"] or 0)
        return counts

    def _full_snapshot(self, db: Session, to_cursor: int, limit_per_entity: int) -> dict[str, list[dict[str, Any]]]:
        del to_cursor
        return {
            str(config["entity"]): self._fetch_rows_for_entity(db, config, None, limit_per_entity)
            for config in self.tables
        }

    def _incremental_changes(
        self,
        db: Session,
        from_cursor: int,
        to_cursor: int,
        limit_per_entity: int,
    ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
        data = {entity: [] for entity in TABLE_ORDER}
        tombstones: list[dict[str, Any]] = []
        rows = db.execute(
            text(
                """
                SELECT id, entity_type, entity_id, operation, changed_at
                FROM client_sync_changes
                WHERE id > :from_cursor AND id <= :to_cursor
                ORDER BY id ASC
                """
            ),
            {"from_cursor": from_cursor, "to_cursor": to_cursor},
        ).mappings().all()

        ids_by_entity: dict[str, set[str]] = {entity: set() for entity in TABLE_ORDER}
        for row in rows:
            entity = str(row["entity_type"])
            if entity not in TABLE_BY_ENTITY:
                continue
            if row["operation"] == "DELETE":
                tombstones.append(
                    {
                        "entity_type": entity,
                        "entity_id": row["entity_id"],
                        "deleted_at": row["changed_at"],
                        "sync_cursor": int(row["id"]),
                    }
                )
            else:
                ids_by_entity[entity].add(str(row["entity_id"]))

        for entity in TABLE_ORDER:
            config = TABLE_BY_ENTITY[entity]
            data[entity] = self._fetch_rows_for_entity(db, config, ids_by_entity[entity], limit_per_entity)
        return data, tombstones

    def _fetch_rows_for_entity(
        self,
        db: Session,
        config: dict[str, Any],
        ids: set[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        table = str(config["table"])
        exclude = set(config.get("exclude", set()))
        excluded_sql = ""
        if exclude:
            excluded_values = ", ".join(f"'{column}'" for column in sorted(exclude))
            excluded_sql = f" - ARRAY[{excluded_values}]"

        if ids is not None and not ids:
            return []

        if ids is None:
            query = text(
                f"""
                SELECT to_jsonb(row_data){excluded_sql} AS payload
                FROM "{table}" AS row_data
                ORDER BY id ASC
                LIMIT :limit
                """
            )
            params: dict[str, Any] = {"limit": max(1, min(limit, 5000))}
        else:
            use_uuid = "uuid" in self._table_columns(db, table) and all(_is_uuid_like(value) for value in ids)
            column_name = "uuid" if use_uuid else "id"
            normalized_ids: list[Any] = [str(value) for value in ids] if use_uuid else [int(value) for value in ids]
            query = text(
                f"""
                SELECT to_jsonb(row_data){excluded_sql} AS payload
                FROM "{table}" AS row_data
                WHERE {"uuid::text" if use_uuid else "id"} = ANY(:ids)
                ORDER BY id ASC
                LIMIT :limit
                """
            )
            params = {"ids": normalized_ids, "limit": max(1, min(limit, 5000))}

        result = []
        for row in db.execute(query, params).mappings().all():
            payload = dict(row["payload"] or {})
            result.append(payload)
        return result

    def _table_columns(self, db: Session, table: str) -> set[str]:
        rows = db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table},
        ).scalars()
        return {str(value) for value in rows}

    def _checksum(self, payload: dict[str, Any]) -> str:
        checksum_payload = {key: value for key, value in payload.items() if key != "checksum_sha256"}
        encoded = json.dumps(checksum_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
