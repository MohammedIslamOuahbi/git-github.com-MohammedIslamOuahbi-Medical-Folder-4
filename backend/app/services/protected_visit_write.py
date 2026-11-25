"""Atomic local medical-visit update, revision, SyncChange, and retry receipt."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.exceptions import ConflictException, ServiceUnavailableException
from app.models.local_revision import LocalEditAttempt, LocalRevision, LocalWriteOperation
from app.models.medical_visit import MedicalVisit
from app.models.sync_change import SyncChange
from app.models.user import User
from app.schemas.medical_visit import MedicalVisitRead
from app.services.sync_journal import serialize_sync_payload, payload_sha256
from app.services.authorization_evidence_service import capture_authorization_execution


def request_fingerprint(action: str, entity_uuid: uuid.UUID, expected_version: int, payload: object) -> str:
    raw = json.dumps(jsonable_encoder({"action": action, "entity_uuid": entity_uuid,
                                      "expected_version": expected_version, "payload": payload}),
                     sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def apply_visit_update(db: Session, user: User, visit: MedicalVisit, *, action: str,
                       expected_version: int, operation_uuid: uuid.UUID,
                       attempted_payload: dict, values: dict,
                       before_commit: Callable[[Session, MedicalVisit], None] | None = None) -> MedicalVisitRead:
    request_hash = request_fingerprint(action, visit.uuid, expected_version, attempted_payload)
    now = datetime.now(timezone.utc)
    db.info["local_operation_uuid"] = operation_uuid
    db.info["stage3_write_contract"] = True
    try:
        previous_attempt = db.get(LocalEditAttempt, operation_uuid)
        if previous_attempt is not None:
            if (previous_attempt.actor_user_uuid != user.uuid or previous_attempt.request_hash != request_hash
                    or previous_attempt.entity_uuid != visit.uuid):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            raise ConflictException("EXPECTED_VERSION_CONFLICT", {"code": "EXPECTED_VERSION_CONFLICT",
                                                                    "attempt_uuid": str(operation_uuid), "attempt_saved": True})
        reserved = db.execute(insert(LocalWriteOperation).values(
            operation_uuid=operation_uuid, actor_user_uuid=user.uuid, request_hash=request_hash,
            entity_type="medical_visits", entity_uuid=visit.uuid, result_payload={}, created_at=now,
        ).on_conflict_do_nothing(index_elements=[LocalWriteOperation.operation_uuid])
          .returning(LocalWriteOperation.operation_uuid)).scalar_one_or_none()
        if reserved is None:
            existing = db.get(LocalWriteOperation, operation_uuid)
            if (existing is None or existing.actor_user_uuid != user.uuid or existing.request_hash != request_hash
                    or existing.entity_uuid != visit.uuid or existing.entity_type != "medical_visits"):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            db.info["local_write_replay"] = True
            payload = existing.result_payload or {}
            return MedicalVisitRead.model_validate(payload.get("result", payload))
        db.info["local_write_replay"] = False

        if visit.status == "validated" or visit.validated_at is not None:
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        previous_sync_version = int(visit.sync_version or 1)
        result = db.execute(update(MedicalVisit).where(
            MedicalVisit.id == visit.id, MedicalVisit.uuid == visit.uuid,
            MedicalVisit.version == expected_version, MedicalVisit.deleted_at.is_(None),
        ).values(**values, version=MedicalVisit.version + 1,
                 sync_version=MedicalVisit.sync_version + 1, sync_status="pending_sync",
                 central_sync_status="central_pending", updated_by=user.id, updated_at=now)
          .returning(MedicalVisit.id)).scalar_one_or_none()
        if result is None:
            db.rollback()  # Discard the reserved operation before preserving the attempt.
            observed = db.scalar(select(MedicalVisit.version).where(MedicalVisit.id == visit.id))
            try:
                existing_attempt = db.get(LocalEditAttempt, operation_uuid)
                if existing_attempt and (existing_attempt.actor_user_uuid != user.uuid or existing_attempt.request_hash != request_hash):
                    raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
                if not existing_attempt:
                    db.add(LocalEditAttempt(
                        operation_uuid=operation_uuid, actor_user_uuid=user.uuid,
                        entity_type="medical_visits", entity_uuid=visit.uuid,
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
            raise ConflictException("EXPECTED_VERSION_CONFLICT", {"code": "EXPECTED_VERSION_CONFLICT",
                                                                    "attempt_uuid": str(operation_uuid), "attempt_saved": True})

        db.expire(visit)
        db.refresh(visit)
        if before_commit is not None:
            before_commit(db, visit)
        baseline_uuid = uuid.uuid4()
        db.execute(insert(LocalRevision).values(
            revision_uuid=baseline_uuid, entity_type="medical_visits", entity_uuid=visit.uuid,
            parent_revision_uuid=None, local_version=previous_sync_version,
            kind="baseline", operation_uuid=None, created_at=now,
        ).on_conflict_do_nothing(constraint="uq_local_revision_version"))
        parent_uuid = db.scalar(select(LocalRevision.revision_uuid).where(
            LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == visit.uuid,
            LocalRevision.local_version == previous_sync_version,
        ))
        revision_uuid = uuid.uuid4()
        db.add(LocalRevision(
            revision_uuid=revision_uuid, entity_type="medical_visits", entity_uuid=visit.uuid,
            parent_revision_uuid=parent_uuid, local_version=visit.sync_version,
            kind="update", operation_uuid=operation_uuid, created_at=now,
        ))
        change = SyncChange(
            change_uuid=uuid.uuid4(), revision_uuid=revision_uuid, operation_uuid=operation_uuid,
            entity_type="medical_visits", entity_uuid=visit.uuid, operation="update",
            base_version=previous_sync_version, parent_revision_uuid=parent_uuid, entity_version=visit.sync_version,
            changed_fields=sorted(values), payload=serialize_sync_payload(visit),
            source_user_uuid=user.uuid, source_device_uuid=db.info.get("sync_source_device_uuid"), source_generation_uuid=db.info.get("sync_source_generation_uuid"), source_clinic_uuid=db.info.get("sync_source_clinic_uuid"), content_sha256=payload_sha256(serialize_sync_payload(visit)), central_status="central_pending", occurred_at=now,
            retry_count=0)
        db.add(change); db.flush()
        capture_authorization_execution(db, user=user, operation=db.get(LocalWriteOperation, operation_uuid), event=change, permission_code="medical_visits.update", scope=f"clinic:{db.info.get('sync_source_clinic_uuid')}:medical_visits:update", policy_version="5A-P1-20261014")
        result_payload = jsonable_encoder(MedicalVisitRead.model_validate(visit))
        db.execute(update(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == operation_uuid)
                   .values(result_payload={**(db.scalar(select(LocalWriteOperation.result_payload).where(LocalWriteOperation.operation_uuid==operation_uuid)) or {}), "result": result_payload}))
        db.commit()
        return MedicalVisitRead.model_validate(result_payload)
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
