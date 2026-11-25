"""Atomic worker update/soft-delete with a linked local revision and SyncChange."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.exceptions import ConflictException, ServiceUnavailableException
from app.models.local_revision import LocalEditAttempt, LocalRevision, LocalWriteOperation
from app.models.sync_change import SyncChange
from app.models.user import User
from app.models.worker import Worker
from app.schemas.worker import WorkerRead
from app.services.protected_visit_write import request_fingerprint
from app.services.sync_journal import serialize_sync_payload, payload_sha256
from app.services.authorization_evidence_service import capture_authorization_execution


def apply_worker_update(db: Session, user: User, worker: Worker, *, action: str,
                        expected_version: int, operation_uuid: uuid.UUID,
                        attempted_payload: dict, values: dict) -> WorkerRead:
    request_hash = request_fingerprint(action, worker.uuid, expected_version, attempted_payload)
    now = datetime.now(timezone.utc)
    worker_uuid, worker_id = worker.uuid, worker.id
    db.info["local_operation_uuid"] = operation_uuid
    db.info["stage3_write_contract"] = True
    try:
        previous_attempt = db.get(LocalEditAttempt, operation_uuid)
        if previous_attempt is not None:
            if (previous_attempt.actor_user_uuid != user.uuid or previous_attempt.request_hash != request_hash
                    or previous_attempt.entity_uuid != worker_uuid):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            raise ConflictException("EXPECTED_VERSION_CONFLICT", {"attempt_uuid": str(operation_uuid), "attempt_saved": True})
        reserved = db.execute(insert(LocalWriteOperation).values(
            operation_uuid=operation_uuid, actor_user_uuid=user.uuid, request_hash=request_hash,
            entity_type="workers", entity_uuid=worker_uuid, result_payload={}, created_at=now,
        ).on_conflict_do_nothing(index_elements=[LocalWriteOperation.operation_uuid])
          .returning(LocalWriteOperation.operation_uuid)).scalar_one_or_none()
        if reserved is None:
            existing = db.get(LocalWriteOperation, operation_uuid)
            if (existing is None or existing.actor_user_uuid != user.uuid or existing.request_hash != request_hash
                    or existing.entity_uuid != worker_uuid or existing.entity_type != "workers"):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            db.info["local_write_replay"] = True
            return WorkerRead.model_validate(existing.result_payload)
        db.info["local_write_replay"] = False
        result = db.execute(update(Worker).where(
            Worker.id == worker_id, Worker.uuid == worker_uuid,
            Worker.sync_version == expected_version, Worker.deleted_at.is_(None),
        ).values(**values, sync_version=Worker.sync_version + 1,
                 sync_status="pending_sync", central_sync_status="central_pending", updated_at=now)
          .returning(Worker.id)).scalar_one_or_none()
        if result is None:
            db.rollback()
            observed = db.scalar(select(Worker.sync_version).where(Worker.id == worker_id))
            try:
                previous = db.get(LocalEditAttempt, operation_uuid)
                if previous and (previous.actor_user_uuid != user.uuid or previous.request_hash != request_hash):
                    raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
                if not previous:
                    db.add(LocalEditAttempt(
                        operation_uuid=operation_uuid, actor_user_uuid=user.uuid,
                        entity_type="workers", entity_uuid=worker_uuid,
                        expected_version=expected_version, observed_version=int(observed or -1),
                        request_hash=request_hash, attempted_payload=jsonable_encoder(attempted_payload),
                        reason_code="STALE_VERSION", created_at=now,
                    ))
                db.commit()
            except ConflictException:
                db.rollback()
                raise
            except Exception as exc:
                db.rollback()
                raise ServiceUnavailableException("EDIT_ATTEMPT_NOT_SAVED") from exc
            raise ConflictException("EXPECTED_VERSION_CONFLICT", {"attempt_uuid": str(operation_uuid), "attempt_saved": True})
        db.expire(worker)
        db.refresh(worker)
        db.execute(insert(LocalRevision).values(
            revision_uuid=uuid.uuid4(), entity_type="workers", entity_uuid=worker_uuid,
            parent_revision_uuid=None, local_version=expected_version,
            kind="baseline", operation_uuid=None, created_at=now,
        ).on_conflict_do_nothing(constraint="uq_local_revision_version"))
        parent_uuid = db.scalar(select(LocalRevision.revision_uuid).where(
            LocalRevision.entity_type == "workers", LocalRevision.entity_uuid == worker_uuid,
            LocalRevision.local_version == expected_version,
        ))
        revision_uuid = uuid.uuid4()
        db.add(LocalRevision(
            revision_uuid=revision_uuid, entity_type="workers", entity_uuid=worker_uuid,
            parent_revision_uuid=parent_uuid, local_version=worker.sync_version,
            kind=action, operation_uuid=operation_uuid, created_at=now,
        ))
        change_row = SyncChange(
            change_uuid=uuid.uuid4(), revision_uuid=revision_uuid, operation_uuid=operation_uuid,
            entity_type="workers", entity_uuid=worker_uuid,
            operation="delete" if action == "delete" else "update",
            base_version=expected_version, parent_revision_uuid=parent_uuid, entity_version=worker.sync_version,
            changed_fields=sorted(values), payload=serialize_sync_payload(worker),
            source_user_uuid=user.uuid,
            source_device_uuid=db.info.get("sync_source_device_uuid"),
            source_generation_uuid=db.info.get("sync_source_generation_uuid"),
            source_clinic_uuid=db.info.get("sync_source_clinic_uuid"),
            content_sha256=payload_sha256(serialize_sync_payload(worker)),
            central_status="central_pending", occurred_at=now, retry_count=0,
        )
        db.add(change_row)
        db.flush()
        capture_authorization_execution(db, user=user, operation=db.get(LocalWriteOperation, operation_uuid), event=change_row, permission_code="workers.update", scope=f"clinic:{db.info.get('sync_source_clinic_uuid')}:workers:update", policy_version="5A-P1-20261014")
        result_payload = jsonable_encoder(WorkerRead.model_validate(worker))
        existing_payload = db.scalar(select(LocalWriteOperation.result_payload).where(LocalWriteOperation.operation_uuid == operation_uuid)) or {}
        db.execute(update(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == operation_uuid)
                   .values(result_payload={**existing_payload, "result": result_payload}))
        db.commit()
        return WorkerRead.model_validate(result_payload)
    except ConflictException:
        if db.in_transaction():
            db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.info.pop("local_operation_uuid", None)
        db.info.pop("stage3_write_contract", None)
