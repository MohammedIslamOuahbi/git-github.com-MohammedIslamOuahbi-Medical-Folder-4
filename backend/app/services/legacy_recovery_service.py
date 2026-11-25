"""Capture legacy evidence into PostgreSQL; never write business tables."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.legacy_recovery import RecoveryIdentityCandidate, RecoveryItem, RecoverySource
from app.models.user import User
from app.services.recovery_format import CaptureValidationError, digest, interpret, validate_envelope

MATERIALIZE_BATCH_SIZE = 100


def is_recovery_admin(user: User) -> bool:
    return bool(user.is_active and (user.role or "").strip().lower() in {"admin", "super_admin"})


def require_access(user: User, source: RecoverySource) -> None:
    if not user.is_active or (not is_recovery_admin(user) and source.captured_by_user_uuid != user.uuid):
        raise ForbiddenException("RECOVERY_ACCESS_DENIED")


def source_summary(source: RecoverySource) -> dict[str, Any]:
    return {
        "uuid": str(source.uuid), "source_kind": source.source_kind,
        "source_identity_present": bool(source.source_identity),
        "format_version": source.format_version,
        "sha256": source.sha256, "byte_length": source.byte_length,
        "parent_source_uuid": str(source.parent_source_uuid) if source.parent_source_uuid else None,
        "state": source.state, "reason_code": source.reason_code,
        "item_count": source.item_count, "materialized_count": source.materialized_count,
        "captured_at": source.captured_at,
    }


class LegacyRecoveryService:
    def capture(self, db: Session, user: User, *, kind: str, logical_key: str,
                profile_id: str, source_identity: str | None, format_version: int,
                raw_payload: str, sha256: str, scope_override: str | None = None) -> RecoverySource:
        if not user.is_active:
            raise ForbiddenException("RECOVERY_ACCESS_DENIED")
        if kind != "browser_local_storage" and not is_recovery_admin(user):
            raise ForbiddenException("RECOVERY_ADMIN_REQUIRED")
        if scope_override and not is_recovery_admin(user):
            raise ForbiddenException("RECOVERY_ADMIN_REQUIRED")
        identity = (source_identity or "").strip() or None
        try:
            byte_length = validate_envelope(kind, format_version, raw_payload, sha256)
            parsed = interpret(kind, raw_payload, identity)
        except CaptureValidationError as exc:
            raise BadRequestException(str(exc)) from None
        if not logical_key or len(logical_key) > 255 or not profile_id or len(profile_id) > 100:
            raise BadRequestException("RECOVERY_SOURCE_KEY_INVALID")
        if identity and len(identity) > 255:
            raise BadRequestException("RECOVERY_SOURCE_IDENTITY_INVALID")
        scope = scope_override or f"user:{user.uuid}:profile:{profile_id}"
        if kind == "legacy_package" and identity and not scope_override:
            scope += ":claimed-origin:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
        if len(scope) > 255:
            raise BadRequestException("RECOVERY_SOURCE_KEY_INVALID")
        capture_hash = digest(raw_payload)
        key = (scope, kind, logical_key)
        existing = db.scalar(select(RecoverySource).where(
            RecoverySource.source_scope == scope, RecoverySource.source_kind == kind,
            RecoverySource.logical_key == logical_key, RecoverySource.sha256 == capture_hash,
        ))
        if existing:
            require_access(user, existing)
            return self.materialize(db, existing)
        parent = db.scalar(select(RecoverySource).where(
            RecoverySource.source_scope == key[0], RecoverySource.source_kind == key[1],
            RecoverySource.logical_key == key[2],
        ).order_by(RecoverySource.captured_at.desc(), RecoverySource.uuid.desc()).limit(1))
        source = RecoverySource(
            uuid=uuid.uuid4(), source_scope=scope, source_identity=identity,
            source_kind=kind, logical_key=logical_key, format_version=format_version,
            sha256=capture_hash, raw_payload=raw_payload, byte_length=byte_length,
            parent_source_uuid=parent.uuid if parent else None,
            captured_by_user_uuid=user.uuid,
            state="needs_review" if parsed.reason_code or not identity else "captured",
            reason_code=parsed.reason_code or ("SOURCE_IDENTITY_MISSING" if not identity else None),
            item_count=len(parsed.items), materialized_count=0,
        )
        db.add(source)
        try:
            db.commit()  # Raw evidence is durable before optional item interpretation.
        except IntegrityError:
            db.rollback()
            source = db.scalar(select(RecoverySource).where(
                RecoverySource.source_scope == scope, RecoverySource.source_kind == kind,
                RecoverySource.logical_key == logical_key, RecoverySource.sha256 == capture_hash,
            ))
            if source is None:
                raise
            require_access(user, source)
        return self.materialize(db, source)

    def materialize(self, db: Session, source: RecoverySource) -> RecoverySource:
        try:
            parsed = interpret(source.source_kind, source.raw_payload, source.source_identity)
        except CaptureValidationError as exc:
            source.state = "needs_review"
            source.reason_code = str(exc)
            db.commit()
            return source
        if parsed.reason_code:
            source.state = "needs_review"
            source.reason_code = parsed.reason_code
            db.commit()
            return source
        start = source.materialized_count
        end = min(start + MATERIALIZE_BATCH_SIZE, source.item_count)
        source_uuid = source.uuid
        try:
            for candidate in parsed.items[start:end]:
                item = RecoveryItem(
                    source_uuid=source_uuid, ordinal=candidate.ordinal, source_ref=candidate.source_ref,
                    raw_fragment=candidate.raw_fragment, entity_type=candidate.entity_type,
                    legacy_id=candidate.legacy_id, entity_uuid=candidate.entity_uuid,
                    state=candidate.state, reason_code=candidate.reason_code,
                )
                db.add(item)
                db.flush()
                if (source.source_kind != "postgres_journal" and candidate.entity_type != "medical_draft"
                        and candidate.legacy_id and candidate.entity_uuid and candidate.entity_type):
                    db.add(RecoveryIdentityCandidate(
                        item_id=item.id, source_scope=source.source_scope,
                        entity_type=candidate.entity_type, legacy_id=candidate.legacy_id,
                        entity_uuid=candidate.entity_uuid, evidence="source_row_uuid",
                        status="candidate_needs_review",
                    ))
                source.materialized_count = candidate.ordinal + 1
            if source.materialized_count >= source.item_count:
                if any(item.state == "needs_review" for item in parsed.items):
                    source.state = "needs_review"
                    source.reason_code = "ITEM_REVIEW_REQUIRED"
                elif not source.source_identity:
                    source.state = "needs_review"
                    source.reason_code = "SOURCE_IDENTITY_MISSING"
                else:
                    source.state = "recorded"
                    source.reason_code = None
            db.add(source)
            db.commit()
        except IntegrityError:
            # A second resume request may have committed the same ordinals first.
            db.rollback()
            current = db.get(RecoverySource, source_uuid)
            if current is None or current.materialized_count < end:
                raise
            return current
        return source

    def resume(self, db: Session, user: User, source_uuid: uuid.UUID) -> RecoverySource:
        source = db.get(RecoverySource, source_uuid)
        if source is None:
            raise NotFoundException("RECOVERY_SOURCE_NOT_FOUND")
        require_access(user, source)
        return self.materialize(db, source)

    def list_sources(self, db: Session, user: User) -> dict[str, Any]:
        if not user.is_active:
            raise ForbiddenException("RECOVERY_ACCESS_DENIED")
        query = select(RecoverySource).order_by(RecoverySource.captured_at.desc()).limit(200)
        if not is_recovery_admin(user):
            query = query.where(RecoverySource.captured_by_user_uuid == user.uuid)
        sources = db.scalars(query).all()
        return {"sources": [source_summary(item) for item in sources], "limited_to": 200}

    def list_item_status(self, db: Session, user: User, source_uuid: uuid.UUID, after: int = -1) -> dict[str, Any]:
        source = db.get(RecoverySource, source_uuid)
        if source is None:
            raise NotFoundException("RECOVERY_SOURCE_NOT_FOUND")
        require_access(user, source)
        items = db.scalars(select(RecoveryItem).where(
            RecoveryItem.source_uuid == source.uuid, RecoveryItem.ordinal > after,
        ).order_by(RecoveryItem.ordinal).limit(100)).all()
        return {"source": source_summary(source), "items": [
            {"ordinal": item.ordinal, "state": item.state, "reason_code": item.reason_code,
             "entity_type": item.entity_type}
            for item in items
        ], "has_more": bool(items and items[-1].ordinal + 1 < source.materialized_count)}

    def capture_journal_page(self, db: Session, user: User, *, table: str, after_id: int, limit: int = 25) -> dict[str, Any]:
        if not is_recovery_admin(user):
            raise ForbiddenException("RECOVERY_ADMIN_REQUIRED")
        from app.models import ClientLocalSyncRun, ClientLocalSyncState, ClientSyncChange, DeviceSyncState, SyncChange, SyncConflict
        from app.models.installation_state import InstallationState
        from sqlalchemy import inspect as sa_inspect

        models = {"sync_changes": SyncChange, "client_sync_changes": ClientSyncChange,
                  "client_local_sync_runs": ClientLocalSyncRun, "client_local_sync_state": ClientLocalSyncState,
                  "device_sync_states": DeviceSyncState, "sync_conflicts": SyncConflict}
        model = models.get(table)
        if model is None or after_id < 0 or not 1 <= limit <= 100:
            raise BadRequestException("RECOVERY_JOURNAL_SOURCE_INVALID")
        identities = db.scalars(select(InstallationState.installation_uuid).limit(2)).all()
        if len(identities) != 1 or not identities[0]:
            raise BadRequestException("RECOVERY_DATABASE_IDENTITY_UNVERIFIED")
        rows = db.scalars(select(model).where(model.id > after_id).order_by(model.id).limit(limit)).all()
        if not rows:
            return {"captured": False, "next_after_id": after_id, "has_more": False}
        payload = {"table": table, "rows": [
            {column.key: jsonable_encoder(getattr(row, column.key)) for column in sa_inspect(type(row)).columns}
            for row in rows
        ]}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        source = self.capture(
            db, user, kind="postgres_journal", logical_key=f"{table}:{rows[0].id}-{rows[-1].id}",
            profile_id="backend", source_identity=str(identities[0]), format_version=1,
            raw_payload=raw, sha256=digest(raw), scope_override=f"database:{identities[0]}",
        )
        return {"captured": True, "source": source_summary(source),
                "next_after_id": rows[-1].id, "has_more": len(rows) == limit}


legacy_recovery_service = LegacyRecoveryService()
