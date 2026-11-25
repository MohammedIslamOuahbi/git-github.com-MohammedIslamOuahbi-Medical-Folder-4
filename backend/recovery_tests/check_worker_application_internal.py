from __future__ import annotations
import os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision, LocalWriteOperation
from app.models.sync_transport import SyncTransportEvent, SyncTransportAttempt
from app.models.sync_change import SyncChange
from app.models.sync_application import SyncApplicationDecision, SyncApplicationAttempt
from app.services.sync_journal import payload_sha256
from app.services.entity_application_service import apply_worker_entity

def _new_event(db):
    company = db.scalar(select(Company).order_by(Company.id))
    if company is None: raise RuntimeError("DEPENDENCY_FIXTURE_COMPANY_MISSING")
    branch = db.scalar(select(Branch).where(Branch.company_id == company.id).order_by(Branch.id))
    if branch is None: raise RuntimeError("DEPENDENCY_FIXTURE_BRANCH_MISSING")
    entity_uuid, event_uuid, operation_uuid, revision_uuid = (uuid.uuid4() for _ in range(4))
    clinic_uuid, device_uuid, generation_uuid = (uuid.uuid4() for _ in range(3))
    payload = {"company_uuid": str(company.uuid), "branch_uuid": str(branch.uuid), "employee_number": f"rollback-{entity_uuid.hex[:12]}", "first_name": "Rollback", "last_name": "Fixture", "gender": "U", "etat_actual": "present", "is_active": True}
    event = SyncTransportEvent(event_uuid=event_uuid, source_clinic_uuid=clinic_uuid, source_device_uuid=device_uuid, source_generation_uuid=generation_uuid, source_sequence=1, entity_type="workers", entity_uuid=entity_uuid, revision_uuid=revision_uuid, operation="insert", schema_version=1, content_sha256=payload_sha256(payload), payload=payload, origin_kind="inbox", created_at=datetime.now(timezone.utc))
    db.add(event); db.commit()
    return SimpleNamespace(**{k: getattr(event, k) for k in ("event_uuid", "source_clinic_uuid", "source_device_uuid", "source_generation_uuid", "source_sequence", "entity_type", "entity_uuid", "revision_uuid", "operation", "schema_version", "content_sha256", "payload", "origin_kind", "created_at")}, operation_uuid=operation_uuid)

def main():
    engine = create_engine(os.environ["STAGE5_TARGET_DB"])
    with Session(engine) as db: event = _new_event(db)
    entity_uuid, revision_uuid = event.entity_uuid, event.revision_uuid
    with Session(engine) as db:
        try: apply_worker_entity(db, event, fail_after_worker_flush=True)
        except RuntimeError as exc:
            assert str(exc) == "INJECTED_ENTITY_APPLICATION_FAILURE_AFTER_WORKER_FLUSH"; db.rollback()
        else: raise AssertionError("injected failure did not occur")
        assert db.info.get("sync_apply_mode") is None and db.info.get("local_operation_uuid") is None
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == entity_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.revision_uuid == revision_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == event.operation_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid == event.event_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid == event.event_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(SyncTransportAttempt).where(SyncTransportAttempt.event_uuid == event.event_uuid)) == 0
        assert db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == entity_uuid)) == 0
    print("failure=after_worker_flush rollback=complete worker=0 revision=0 operation=0 processing=0 syncchange=0")
    with Session(engine) as db:
        assert apply_worker_entity(db, event).uuid == entity_uuid
        assert db.info.get("sync_apply_mode") is None
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == entity_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.revision_uuid == revision_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == event.operation_uuid)) == 1
    print("retry=accepted_test_only worker=1 revision=1 operation=1 business_tables_changed_in_test=1")
    with Session(engine) as db:
        assert apply_worker_entity(db, event).uuid == entity_uuid
        assert db.info.get("sync_apply_mode") is None
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == entity_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.revision_uuid == revision_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == event.operation_uuid)) == 1
    print("replay=deduplicated worker=1 revision=1 operation=1")

if __name__ == "__main__": main()
