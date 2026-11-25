from __future__ import annotations

from app.services.sync_safety import suspend_for_data_safety

import hashlib
import json
import uuid as py_uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import *  # noqa: F401,F403 - ensure all tables are registered for local-copy import
from app.models.client_local_sync import ClientLocalSyncRun, ClientLocalSyncState
from app.services.client_sync_service import CLIENT_SYNC_SCHEMA_VERSION, TABLE_BY_ENTITY, TABLE_ORDER
from app.services.server_identity import API_VERSION

APP_ID = "medical-folder"
MAX_PACKAGE_SIZE_BYTES = 512 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".sync", ".json"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _checksum(payload: dict[str, Any]) -> str:
    checksum_payload = {key: value for key, value in payload.items() if key != "checksum_sha256"}
    encoded = json.dumps(checksum_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _table_for_entity(entity: str):
    config = TABLE_BY_ENTITY.get(entity)
    if not config:
        raise ValueError(f"SYNC_PACKAGE_INVALID:UNKNOWN_ENTITY:{entity}")
    return Base.metadata.tables[str(config["table"])]


def _permitted_row(table, row: dict[str, Any]) -> dict[str, Any]:
    columns = set(table.c.keys())
    return {key: value for key, value in row.items() if key in columns and key != "sync_cursor"}


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _is_uuid_like(value: Any) -> bool:
    try:
        py_uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True

def ensure_snapshot_update_allowed(*, table_name: str, exists: bool, has_uuid: bool) -> None:
    """Snapshot import may not overwrite an existing sync entity without the event contract."""
    if exists and has_uuid and table_name not in {"client_local_sync_state", "client_local_sync_runs"}:
        raise ValueError("SYNC_APPLICATION_CONTRACT_REQUIRED")


class ClientSyncImportService:
    def _load_package_payload(self, package_path: str | Path) -> tuple[Path, dict[str, Any], str]:
        path = Path(package_path).resolve()
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("SYNC_PACKAGE_INVALID")
        if not path.exists() or not path.is_file():
            raise ValueError("SYNC_PACKAGE_INVALID")
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_PACKAGE_SIZE_BYTES:
            raise ValueError("SYNC_PACKAGE_INVALID")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("SYNC_PACKAGE_INVALID") from exc

        if not isinstance(payload, dict):
            raise ValueError("SYNC_PACKAGE_INVALID")
        checksum = str(payload.get("checksum_sha256") or "")
        if not checksum or _checksum(payload) != checksum:
            raise ValueError("SYNC_CHECKSUM_FAILED")
        return path, payload, checksum

    def _validate_payload(self, payload: dict[str, Any], expected_server_id: str | None = None) -> dict[str, Any]:
        if payload.get("application") != APP_ID:
            raise ValueError("SYNC_PACKAGE_INVALID")
        if payload.get("mode") != "SERVER_TO_CLIENT_ONLY":
            raise ValueError("SYNC_PACKAGE_INVALID")
        if int(payload.get("schema_version") or 0) != CLIENT_SYNC_SCHEMA_VERSION:
            raise ValueError("SYNC_SCHEMA_MISMATCH")

        package_version = str(payload.get("application_version") or payload.get("api_version") or "")
        if package_version and package_version != API_VERSION:
            raise ValueError("SYNC_APP_VERSION_MISMATCH")

        server_id = str(payload.get("server_id") or "")
        if not server_id:
            raise ValueError("SYNC_PACKAGE_INVALID")
        if expected_server_id and expected_server_id != server_id:
            raise ValueError("SYNC_SERVER_IDENTITY_MISMATCH")

        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("SYNC_PACKAGE_INVALID")
        unknown_entities = set(data.keys()) - set(TABLE_BY_ENTITY.keys())
        if unknown_entities:
            raise ValueError(f"SYNC_PACKAGE_INVALID:UNKNOWN_ENTITY:{sorted(unknown_entities)[0]}")

        tombstones = payload.get("tombstones") or []
        if not isinstance(tombstones, list):
            raise ValueError("SYNC_PACKAGE_INVALID")

        record_counts = payload.get("record_counts") or {}
        if not isinstance(record_counts, dict):
            raise ValueError("SYNC_PACKAGE_INVALID")

        created_at = _parse_iso_datetime(payload.get("created_at") or payload.get("generated_at"))
        return {
            "server_id": server_id,
            "from_cursor": int(payload.get("from_cursor") or 0),
            "to_cursor": int(payload.get("to_cursor") or 0),
            "package_id": str(payload.get("package_id") or payload.get("checksum_sha256") or ""),
            "workspace": payload.get("workspace") or {"id": None, "name": "Global"},
            "created_at": created_at,
            "application_version": package_version or API_VERSION,
            "schema_version": int(payload.get("schema_version") or 0),
            "data": data,
            "tombstones": tombstones,
            "record_counts": record_counts,
            "attachment_manifest": payload.get("attachments") or [],
            "server_identity": payload.get("server_identity") or {},
            "manifest": payload,
        }

    def inspect_package(
        self,
        db: Session,
        package_path: str | Path,
        expected_server_id: str | None = None,
        *,
        allow_reimport_cursor_window: bool = False,
    ) -> dict[str, Any]:
        path, payload, checksum = self._load_package_payload(package_path)
        meta = self._validate_payload(payload, expected_server_id=expected_server_id)
        current_state = db.get(ClientLocalSyncState, 1)
        duplicate = (
            db.execute(
                select(ClientLocalSyncRun.id).where(
                    ClientLocalSyncRun.checksum_sha256 == checksum,
                    ClientLocalSyncRun.status == "COMPLETED",
                )
            ).first()
            is not None
        )
        if current_state and current_state.server_id != meta["server_id"]:
            raise ValueError("SYNC_SERVER_IDENTITY_MISMATCH")
        if current_state and meta["from_cursor"] < int(current_state.last_sync_cursor or 0) and not allow_reimport_cursor_window:
            raise ValueError("SYNC_CURSOR_ROLLBACK_REJECTED")

        counts = {entity: int(meta["record_counts"].get(entity) or len(meta["data"].get(entity) or [])) for entity in TABLE_ORDER}
        summary = {
            "server": meta["server_identity"].get("server_id") or meta["server_id"],
            "workspace": meta["workspace"].get("name") if isinstance(meta["workspace"], dict) else str(meta["workspace"]),
            "created": meta["created_at"].isoformat() if meta["created_at"] else None,
            "application_version": meta["application_version"],
            "schema_version": meta["schema_version"],
            "workers": counts.get("workers", 0),
            "visits": counts.get("medical_visits", 0),
            "certificates": counts.get("orientation_certificates", 0) + counts.get("aptitude_certificates", 0),
            "medical_tests": counts.get("medical_tests", 0) + counts.get("worker_tests", 0),
            "companies": counts.get("companies", 0),
            "campaigns": counts.get("medical_campaigns", 0),
            "users": counts.get("users", 0),
            "total_changes": sum(counts.values()) + len(meta["tombstones"]),
        }
        return {
            "valid": True,
            "package_id": meta["package_id"],
            "package_name": path.name,
            "checksum_sha256": checksum,
            "server_id": meta["server_id"],
            "from_cursor": meta["from_cursor"],
            "to_cursor": meta["to_cursor"],
            "created_at": summary["created"],
            "application_version": meta["application_version"],
            "schema_version": meta["schema_version"],
            "workspace": meta["workspace"],
            "server_identity": meta["server_identity"],
            "record_counts": counts,
            "tombstone_count": len(meta["tombstones"]),
            "attachment_count": len(meta["attachment_manifest"]) if isinstance(meta["attachment_manifest"], list) else 0,
            "duplicate": duplicate,
            "summary": summary,
        }

    def history(self, db: Session, limit: int = 20) -> list[dict[str, Any]]:
        rows = (
            db.execute(
                select(ClientLocalSyncRun)
                .order_by(ClientLocalSyncRun.started_at.desc(), ClientLocalSyncRun.id.desc())
                .limit(max(1, min(limit, 100)))
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": row.id,
                "package_id": row.package_id,
                "package_name": row.package_name,
                "date": row.completed_at.isoformat() if row.completed_at else row.started_at.isoformat(),
                "duration_ms": row.duration_ms,
                "rows_imported": row.inserted_count,
                "rows_updated": row.updated_count,
                "rows_skipped": row.skipped_count,
                "attachments_imported": row.attachment_count,
                "checksum_sha256": row.checksum_sha256,
                "status": row.status,
                "server_id": row.server_id,
                "from_cursor": row.from_cursor,
                "to_cursor": row.to_cursor,
                "deleted_count": row.deleted_count,
                "error_code": row.error_code,
            }
            for row in rows
        ]

    def local_status(self, db: Session) -> dict[str, Any]:
        state = db.get(ClientLocalSyncState, 1)
        latest_run = (
            db.execute(select(ClientLocalSyncRun).order_by(ClientLocalSyncRun.started_at.desc(), ClientLocalSyncRun.id.desc()).limit(1))
            .scalars()
            .first()
        )
        totals = db.execute(
            select(
                func.count(ClientLocalSyncRun.id),
                func.coalesce(func.sum(ClientLocalSyncRun.inserted_count), 0),
                func.coalesce(func.sum(ClientLocalSyncRun.updated_count), 0),
                func.coalesce(func.sum(ClientLocalSyncRun.skipped_count), 0),
            )
        ).first()
        return {
            "configured": True,
            "server_id": state.server_id if state else None,
            "last_sync_cursor": int(state.last_sync_cursor) if state else 0,
            "last_sync_at": state.last_sync_at.isoformat() if state and state.last_sync_at else None,
            "last_package_id": state.last_package_id if state else None,
            "last_package_name": state.last_package_name if state else None,
            "last_imported_at": state.last_imported_at.isoformat() if state and state.last_imported_at else None,
            "last_package_checksum": state.last_package_checksum if state else None,
            "schema_version": int(state.schema_version) if state else CLIENT_SYNC_SCHEMA_VERSION,
            "last_status": state.last_status if state else "IDLE",
            "history_count": int(totals[0] or 0) if totals else 0,
            "imported_rows_total": int((totals[1] or 0) + (totals[2] or 0)) if totals else 0,
            "skipped_rows_total": int(totals[3] or 0) if totals else 0,
            "latest_run": {
                "package_name": latest_run.package_name,
                "package_id": latest_run.package_id,
                "status": latest_run.status,
                "date": latest_run.completed_at.isoformat() if latest_run and latest_run.completed_at else None,
            }
            if latest_run
            else None,
        }

    def _record_failed_run(
        self,
        db: Session,
        *,
        server_id: str,
        package_id: str | None,
        package_name: str,
        checksum_sha256: str | None,
        from_cursor: int,
        to_cursor: int,
        started_at: datetime,
        error_code: str,
    ) -> None:
        db.add(
            ClientLocalSyncRun(
                server_id=server_id or "unknown",
                from_cursor=from_cursor,
                to_cursor=to_cursor,
                started_at=started_at,
                completed_at=_utcnow(),
                package_id=package_id,
                package_name=package_name,
                checksum_sha256=checksum_sha256,
                duration_ms=0,
                inserted_count=0,
                updated_count=0,
                deleted_count=0,
                skipped_count=0,
                file_count=0,
                attachment_count=0,
                status="FAILED",
                error_code=error_code,
            )
        )
        db.commit()

    def import_package(self, db: Session, package_path: str | Path, expected_server_id: str | None = None) -> dict[str, Any]:
        suspend_for_data_safety("client_package_import")
        started_at = _utcnow()
        path = Path(package_path).resolve()
        checksum: str | None = None
        meta: dict[str, Any] | None = None
        try:
            path, payload, checksum = self._load_package_payload(path)
            meta = self._validate_payload(payload, expected_server_id=expected_server_id)
            current_state = db.get(ClientLocalSyncState, 1)
            if current_state and current_state.server_id != meta["server_id"]:
                raise ValueError("SYNC_SERVER_IDENTITY_MISMATCH")
            duplicate = db.execute(
                select(ClientLocalSyncRun.id).where(
                    ClientLocalSyncRun.checksum_sha256 == checksum,
                    ClientLocalSyncRun.status == "COMPLETED",
                )
            ).first()
            if duplicate:
                raise ValueError("SYNC_ALREADY_IMPORTED")
            if current_state and meta["from_cursor"] < int(current_state.last_sync_cursor or 0):
                raise ValueError("SYNC_CURSOR_ROLLBACK_REJECTED")

            inserted_count = 0
            updated_count = 0
            deleted_count = 0
            skipped_count = 0
            attachment_count = 0
            db.info["skip_client_sync_journal"] = True

            with db.begin_nested():
                for entity in TABLE_ORDER:
                    rows = meta["data"].get(entity) or []
                    if not isinstance(rows, list):
                        raise ValueError(f"SYNC_PACKAGE_INVALID:INVALID_ENTITY_PAYLOAD:{entity}")
                    table = _table_for_entity(entity)
                    for row in rows:
                        if not isinstance(row, dict):
                            raise ValueError(f"SYNC_PACKAGE_INVALID:INVALID_ROW:{entity}")
                        values = _permitted_row(table, row)
                        if "id" not in values:
                            raise ValueError(f"SYNC_PACKAGE_INVALID:MISSING_ID:{entity}")
                        conflict_column = table.c.uuid if "uuid" in table.c and values.get("uuid") else table.c.id
                        if conflict_column is not table.c.id and "id" in values:
                            values.pop("id", None)
                        protected_update_fields: set[str] = set()
                        if table.name == "users" and "password_hash" in table.c and "password_hash" not in values:
                            values["password_hash"] = "LOCAL_COPY_AUTH_DISABLED"
                            protected_update_fields.add("password_hash")
                        existing_lookup_column = conflict_column
                        existing_lookup_value = values.get(existing_lookup_column.name)
                        exists = (
                            db.execute(select(table.c.id).where(existing_lookup_column == existing_lookup_value)).first()
                            is not None
                        )
                        # Snapshot imports do not carry the event's base
                        # revision.  Never let ON CONFLICT turn that absence
                        # into an implicit overwrite of local work (or a
                        # signed row); such updates must use the guarded
                        # application contract instead.
                        ensure_snapshot_update_allowed(table_name=table.name, exists=exists, has_uuid="uuid" in table.c)
                        update_values = {
                            key: pg_insert(table).excluded[key]
                            for key in values
                            if key not in {"id", conflict_column.name} and key not in protected_update_fields
                        }
                        statement = pg_insert(table).values(**values)
                        statement = (
                            statement.on_conflict_do_update(index_elements=[conflict_column], set_=update_values)
                            if update_values
                            else statement.on_conflict_do_nothing(index_elements=[conflict_column])
                        )
                        db.execute(statement)
                        if exists:
                            updated_count += 1
                        else:
                            inserted_count += 1

                for tombstone in sorted(
                    meta["tombstones"],
                    key=lambda item: TABLE_ORDER.index(item["entity_type"]) if item.get("entity_type") in TABLE_ORDER else -1,
                    reverse=True,
                ):
                    entity = str(tombstone.get("entity_type") or "")
                    table = _table_for_entity(entity)
                    entity_id = tombstone.get("entity_id")
                    match_column = table.c.uuid if "uuid" in table.c and _is_uuid_like(entity_id) else table.c.id
                    if "deleted_at" in table.c:
                        db.execute(
                            table.update()
                            .where(match_column == entity_id)
                            .values(deleted_at=tombstone.get("deleted_at") or _utcnow())
                        )
                    else:
                        db.execute(table.delete().where(match_column == entity_id))
                    deleted_count += 1

                completed_at = _utcnow()
                state_values = {
                    "id": 1,
                    "server_id": meta["server_id"],
                    "last_sync_cursor": meta["to_cursor"],
                    "last_sync_at": completed_at,
                    "schema_version": CLIENT_SYNC_SCHEMA_VERSION,
                    "last_package_checksum": checksum,
                    "last_package_id": meta["package_id"],
                    "last_package_name": path.name,
                    "last_imported_at": completed_at,
                    "last_status": "COMPLETED",
                }
                db.execute(
                    pg_insert(ClientLocalSyncState.__table__)
                    .values(**state_values)
                    .on_conflict_do_update(
                        index_elements=[ClientLocalSyncState.__table__.c.id],
                        set_={key: value for key, value in state_values.items() if key != "id"},
                    )
                )
                db.add(
                    ClientLocalSyncRun(
                        server_id=meta["server_id"],
                        from_cursor=meta["from_cursor"],
                        to_cursor=meta["to_cursor"],
                        started_at=started_at,
                        completed_at=completed_at,
                        package_id=meta["package_id"],
                        package_name=path.name,
                        checksum_sha256=checksum,
                        duration_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
                        inserted_count=inserted_count,
                        updated_count=updated_count,
                        deleted_count=deleted_count,
                        skipped_count=skipped_count,
                        file_count=0,
                        attachment_count=attachment_count,
                        status="COMPLETED",
                        error_code=None,
                    )
                )
        except ValueError as exc:
            db.rollback()
            if meta is not None or checksum is not None:
                try:
                    self._record_failed_run(
                        db,
                        server_id=(meta or {}).get("server_id", ""),
                        package_id=(meta or {}).get("package_id"),
                        package_name=path.name,
                        checksum_sha256=checksum,
                        from_cursor=int((meta or {}).get("from_cursor") or 0),
                        to_cursor=int((meta or {}).get("to_cursor") or 0),
                        started_at=started_at,
                        error_code=str(exc),
                    )
                except Exception:
                    db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            try:
                self._record_failed_run(
                    db,
                    server_id=(meta or {}).get("server_id", ""),
                    package_id=(meta or {}).get("package_id"),
                    package_name=path.name,
                    checksum_sha256=checksum,
                    from_cursor=int((meta or {}).get("from_cursor") or 0),
                    to_cursor=int((meta or {}).get("to_cursor") or 0),
                    started_at=started_at,
                    error_code="SYNC_TRANSACTION_FAILED",
                )
            except Exception:
                db.rollback()
            raise ValueError("SYNC_TRANSACTION_FAILED") from exc
        finally:
            db.info.pop("skip_client_sync_journal", None)

        db.commit()
        completed = self.inspect_package(db, path, allow_reimport_cursor_window=True)
        return {
            "success": True,
            "server_id": completed["server_id"],
            "from_cursor": completed["from_cursor"],
            "to_cursor": completed["to_cursor"],
            "inserted_count": inserted_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "file_count": 0,
            "attachment_count": 0,
            "checksum_sha256": checksum,
            "package_id": completed["package_id"],
            "package_name": completed["package_name"],
            "message": "Package de synchronisation importe.",
            "summary": completed["summary"],
        }
