"""Restricted entity-application primitives; not exposed as an endpoint."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.worker import Worker
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision
from app.models.sync_conflict import SyncConflict
from app.models.local_revision import LocalEditAttempt
from app.models.local_revision import LocalWriteOperation
from app.services.sync_application_evaluation_service import resolve_event_dependencies

def apply_verified_worker_entity(db: Session, event, *, decision, current_input_fingerprint: str,
                                 fail_after_worker_flush: bool = False):
    """Test-only orchestration boundary; production application guards stay closed.

    The decision must be re-read from durable evaluation state by the caller and
    its fingerprint must still describe the current evidence.  A client flag is
    never accepted as authorization.
    """
    if decision is None or decision.decision != "accepted_test_only":
        raise PermissionError("APPLICATION_DECISION_NOT_ELIGIBLE")
    if decision.input_fingerprint != current_input_fingerprint:
        raise PermissionError("APPLICATION_EVIDENCE_STALE")
    deps = resolve_event_dependencies(db, event)
    if (not deps["company"]["matched"] or not deps["branch"]["matched"]
            or not deps["branch"].get("belongs_to_company", False)):
        raise ValueError("DEPENDENCY_MISSING")
    return apply_worker_entity(db, event, fail_after_worker_flush=fail_after_worker_flush)

def apply_from_reconciliation_result(db: Session, event, *, reconciliation_result,
                                     current_input_fingerprint: str,
                                     freshness_revalidator=None,
                                     fail_after_worker_flush: bool = False):
    """Consume a verified reconciliation result in the isolated test runner.

    This deliberately does not translate ``evaluate_event``'s production
    blocked decisions.  The result must come from the reconciliation verifier
    and carry its current evidence fingerprint.
    """
    if not isinstance(reconciliation_result, dict) or reconciliation_result.get("status") != "accepted_test_only":
        raise PermissionError("RECONCILIATION_RESULT_NOT_ACCEPTED")
    verification = reconciliation_result.get("verification") or {}
    if reconciliation_result.get("business_application") != 0:
        raise PermissionError("RECONCILIATION_APPLICATION_SCOPE_INVALID")
    result_fp = verification.get("input_fingerprint") or reconciliation_result.get("input_fingerprint")
    if not result_fp or result_fp != current_input_fingerprint:
        raise PermissionError("RECONCILIATION_EVIDENCE_STALE")
    if not callable(freshness_revalidator) or not freshness_revalidator():
        raise PermissionError("FRESHNESS_REVALIDATION_REQUIRED")
    return apply_worker_entity(db, event, fail_after_worker_flush=fail_after_worker_flush)

def apply_worker_entity(db: Session, event, *, fail_after_worker_flush: bool = False):
    deps = resolve_event_dependencies(db, event)
    if not deps["company"]["matched"] or not deps["branch"]["matched"] or not deps["branch"].get("belongs_to_company", False):
        raise ValueError("DEPENDENCY_MISSING")
    existing = db.scalar(select(Worker).where(Worker.uuid == event.entity_uuid))
    if existing is not None:
        return existing
    op = getattr(event, "operation_uuid", None) or uuid.uuid4()
    previous = {k: db.info.get(k) for k in ("local_operation_uuid", "stage3_write_contract", "sync_apply_mode")}
    db.info.update(local_operation_uuid=op, stage3_write_contract=True, sync_apply_mode=True)
    try:
        # Incoming application is attributed to the authenticated source device,
        # never to an arbitrary local user.  The column is non-null by schema.
        actor = getattr(event, "source_device_uuid", None) or uuid.UUID(int=0)
        db.add(LocalWriteOperation(operation_uuid=op, actor_user_uuid=actor, request_hash="incoming-entity-application", entity_type="workers", entity_uuid=event.entity_uuid, result_payload={"incoming": True}, created_at=datetime.now(timezone.utc)))
        db.flush()
        payload = event.payload
        row = Worker(uuid=event.entity_uuid, company_id=deps["company"]["local_id"], branch_id=deps["branch"]["local_id"], employee_number=payload["employee_number"], first_name=payload["first_name"], last_name=payload["last_name"], gender=payload.get("gender"), etat_actual=payload.get("etat_actual"), is_active=payload.get("is_active", True))
        db.add(row); db.flush()
        if fail_after_worker_flush:
            raise RuntimeError("INJECTED_ENTITY_APPLICATION_FAILURE_AFTER_WORKER_FLUSH")
        db.add(LocalRevision(revision_uuid=event.revision_uuid, entity_type="workers", entity_uuid=event.entity_uuid, local_version=event.source_sequence or 1, kind="insert", operation_uuid=op, created_at=datetime.now(timezone.utc)))
        db.commit()
        return row
    except Exception:
        # The caller owns the transaction boundary; rollback here only clears
        # the failed unit of work and never marks a partial application.
        db.rollback()
        raise
    finally:
        for key, value in previous.items():
            if value is None: db.info.pop(key, None)
            else: db.info[key] = value

def apply_medical_visit_entity(db: Session, event, *, fail_after_visit_flush: bool = False):
    """Restricted internal application primitive for an unsigned visit insert."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    worker_uuid = payload.get("worker_uuid")
    worker = None
    if worker_uuid:
        worker = db.scalar(select(Worker).where(Worker.uuid == uuid.UUID(str(worker_uuid))))
    if worker is None:
        raise ValueError("DEPENDENCY_MISSING_WORKER")
    existing = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == event.entity_uuid))
    if existing is not None:
        return {"status": "replay", "visit_uuid": str(existing.uuid)}
    op = getattr(event, "operation_uuid", None) or uuid.uuid4()
    prior = db.scalar(select(LocalRevision).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == event.entity_uuid, LocalRevision.operation_uuid == op))
    if prior is not None:
        return {"status": "replay", "visit_uuid": str(event.entity_uuid)}
    previous = db.info.get("sync_apply_mode")
    db.info["sync_apply_mode"] = True
    try:
        row = MedicalVisit(uuid=event.entity_uuid, worker_id=worker.id, worker_uuid=worker.uuid,
            campaign_id=None, campaign_uuid=payload.get("campaign_uuid"), visit_date=payload["visit_date"],
            site_name=payload.get("site_name"), status=payload.get("status", "draft"),
            form_data=payload.get("form_data"), sync_status="pending_sync", version=1)
        db.add(row); db.flush()
        if fail_after_visit_flush:
            raise RuntimeError("INJECTED_VISIT_APPLICATION_FAILURE_AFTER_FLUSH")
        db.add(LocalRevision(revision_uuid=event.revision_uuid, entity_type="medical_visits", entity_uuid=event.entity_uuid,
            local_version=1, kind="insert", operation_uuid=op, created_at=datetime.now(timezone.utc)))
        db.commit()
        return {"status": "applied", "visit_uuid": str(row.uuid)}
    except Exception:
        db.rollback(); raise
    finally:
        if previous is None: db.info.pop("sync_apply_mode", None)
        else: db.info["sync_apply_mode"] = previous

def apply_medical_visit_update_entity(db: Session, event, *, fail_after_visit_flush: bool = False):
    payload = event.payload if isinstance(event.payload, dict) else {}
    row = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == event.entity_uuid))
    if row is None: raise ValueError("TARGET_VISIT_MISSING")
    if row.status == "validated" or row.validated_at is not None:
        raise ValueError("SIGNED_DOCUMENT_IMMUTABLE")
    current = db.scalar(select(LocalRevision).where(LocalRevision.entity_type=="medical_visits", LocalRevision.entity_uuid==event.entity_uuid).order_by(LocalRevision.local_version.desc()))
    current_version = current.local_version if current else int(row.version or 1)
    base = getattr(event, "base_version", None)
    op=getattr(event,"operation_uuid",None); prior=db.scalar(select(LocalRevision).where(LocalRevision.entity_uuid==event.entity_uuid,LocalRevision.operation_uuid==op)) if op else None
    if prior: return {"status":"replay","version":prior.local_version}
    if base != current_version:
        existing=db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid==event.event_uuid, SyncConflict.entity_uuid==event.entity_uuid))
        if existing: return {"status":"conflict","reason":"CONFLICT_ALREADY_RECORDED"}
        db.add(SyncConflict(incoming_change_uuid=event.event_uuid,entity_type="medical_visits",entity_uuid=event.entity_uuid,source_device_uuid=getattr(event,"source_device_uuid",None),base_version=base,central_version=current_version,central_snapshot={"site_name":row.site_name,"status":row.status},mission_snapshot=dict(payload),conflicting_fields=list(payload),status="physician_review")); db.commit(); return {"status":"conflict","reason":"BASE_VERSION_MISMATCH"}
    previous=db.info.get("sync_apply_mode"); db.info["sync_apply_mode"]=True
    try:
        for key in ("visit_date","site_name","status","form_data","doctor_notes"):
            if key in payload: setattr(row,key,payload[key])
        row.version=current_version+1; row.sync_version=current_version+1; db.flush()
        if fail_after_visit_flush: raise RuntimeError("INJECTED_VISIT_UPDATE_FAILURE_AFTER_FLUSH")
        db.add(LocalRevision(revision_uuid=event.revision_uuid,entity_type="medical_visits",entity_uuid=event.entity_uuid,parent_revision_uuid=getattr(event,"parent_revision_uuid",None),local_version=current_version+1,kind="update",operation_uuid=op,created_at=datetime.now(timezone.utc))); db.commit(); return {"status":"applied","version":current_version+1}
    except Exception: db.rollback(); raise
    finally:
        if previous is None: db.info.pop("sync_apply_mode",None)
        else: db.info["sync_apply_mode"]=previous

def apply_worker_update_entity(db: Session, event, *, fail_after_worker_flush: bool = False):
    """Apply an already verified Worker update in the isolated application runner."""
    deps = resolve_event_dependencies(db, event)
    if not deps["company"]["matched"] or not deps["branch"]["matched"] or not deps["branch"].get("belongs_to_company", False):
        raise ValueError("DEPENDENCY_MISSING")
    row = db.scalar(select(Worker).where(Worker.uuid == event.entity_uuid))
    if row is None: raise ValueError("TARGET_ENTITY_MISSING")
    # Idempotency is keyed by the incoming operation, never by the latest row.
    # A replay must not create another revision or mutate the entity again.
    operation_uuid = getattr(event, "operation_uuid", None)
    if operation_uuid is not None:
        prior = db.scalar(select(LocalRevision).where(
            LocalRevision.entity_type == "workers",
            LocalRevision.entity_uuid == event.entity_uuid,
            LocalRevision.operation_uuid == operation_uuid,
        ))
        if prior is not None:
            if prior.revision_uuid != getattr(event, "revision_uuid", None):
                raise ValueError("OPERATION_UUID_REUSED_WITH_DIFFERENT_EVENT")
            return {"status": "replay", "version": prior.local_version,
                    "revision_uuid": str(prior.revision_uuid)}
    current = db.scalar(select(LocalRevision).where(LocalRevision.entity_uuid == event.entity_uuid).order_by(LocalRevision.local_version.desc()))
    current_version = current.local_version if current else 0
    base = getattr(event, "base_version", None)
    pending = db.scalar(select(LocalEditAttempt).where(LocalEditAttempt.entity_uuid == event.entity_uuid, LocalEditAttempt.reason_code != "APPLIED"))
    if base != current_version or pending is not None:
        existing_conflict = db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid == event.event_uuid, SyncConflict.entity_uuid == event.entity_uuid))
        if existing_conflict is not None:
            return {"status":"conflict","reason":existing_conflict.blocking_reason or "CONFLICT_ALREADY_RECORDED"}
        db.add(SyncConflict(incoming_change_uuid=event.event_uuid, entity_type="workers", entity_uuid=event.entity_uuid, source_device_uuid=getattr(event,"source_device_uuid",None), base_version=base, central_version=current_version, central_snapshot={"first_name":row.first_name,"last_name":row.last_name}, mission_snapshot=dict(event.payload), conflicting_fields=list(event.payload), status="pending")); db.flush(); db.commit(); return {"status":"conflict","reason":"BASE_VERSION_MISMATCH"}
    previous = {k: db.info.get(k) for k in ("sync_apply_mode",)}; db.info["sync_apply_mode"] = True
    try:
        for key in ("first_name","last_name","gender","etat_actual","is_active"):
            if key in event.payload: setattr(row,key,event.payload[key])
        row.sync_version = current_version + 1
        db.flush()
        if fail_after_worker_flush: raise RuntimeError("INJECTED_ENTITY_APPLICATION_FAILURE_AFTER_WORKER_FLUSH")
        db.add(LocalRevision(revision_uuid=event.revision_uuid, entity_type="workers", entity_uuid=event.entity_uuid, local_version=current_version+1, kind="update", operation_uuid=operation_uuid, created_at=datetime.now(timezone.utc))); db.commit(); return {"status":"applied","version":current_version+1}
    except Exception:
        db.rollback(); raise
    finally:
        if previous["sync_apply_mode"] is None: db.info.pop("sync_apply_mode",None)
        else: db.info["sync_apply_mode"] = previous["sync_apply_mode"]
