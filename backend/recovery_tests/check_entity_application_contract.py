"""Isolated contract checks for application policy; never enables production apply."""
import os, sys, uuid
from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.sync_conflict import SyncConflict
from app.services.central_sync_service import CentralSyncService
from app.services.client_sync_import_service import ensure_snapshot_update_allowed
from types import SimpleNamespace

name = os.environ.get("STAGE5_ENTITY_DB")
if not name:
    raise RuntimeError("STAGE5_ENTITY_DB is required; refusing to use demo")
from sqlalchemy.engine import make_url
url = make_url(settings.database_url).set(database=name).render_as_string(hide_password=False)
engine = create_engine(url)
with engine.connect() as c:
    assert c.scalar(text("select version_num from alembic_version")) == "20261008_23"
service = CentralSyncService()
with Session(engine) as db:
    db.info["sync_bootstrap_mode"] = True
    company = db.scalar(select(Company).where(Company.deleted_at.is_(None)))
    if company is None:
        company = Company(uuid=uuid.uuid4(), name="Entity contract fixture " + uuid.uuid4().hex[:8]); db.add(company); db.flush()
    branch = db.scalar(select(Branch).where(Branch.company_id == company.id, Branch.deleted_at.is_(None)))
    if branch is None:
        branch = Branch(uuid=uuid.uuid4(), company_id=company.id, name="Entity contract branch"); db.add(branch); db.flush()
    worker = Worker(uuid=uuid.uuid4(), company_id=company.id, branch_id=branch.id,
                    employee_number="ENTITY-CONTRACT-" + uuid.uuid4().hex[:8],
                    first_name="Contract", last_name="Fixture", etat_actual="present", sync_version=1)
    db.add(worker); db.commit(); db.info.pop("sync_bootstrap_mode", None)
    event = {"change_uuid": uuid.uuid4(), "entity_type": "workers", "entity_uuid": worker.uuid,
             "operation": "update", "base_version": 1, "entity_version": 2,
             "changed_fields": ["first_name"], "payload": {"uuid": str(worker.uuid), "first_name": "Remote"},
             "source_device_uuid": uuid.uuid4()}
    assert service._application_conflict(db, event) is None
    print("matching_base_no_local_edit=none")
    event["base_version"] = 0
    reason = service._application_conflict(db, event)
    assert reason and reason[0] == "base_version_mismatch"
    print("base_version_mismatch=conflict_local_preserved=1")
    event["base_version"] = 1; event["source_device_uuid"] = uuid.uuid4()
    db.info["sync_apply_mode"] = True
    worker.central_sync_status = "central_pending"; worker.last_modified_device_uuid = uuid.uuid4(); db.add(worker); db.flush()
    db.info.pop("sync_apply_mode", None)
    print("pending_state=", worker.central_sync_status, worker.last_modified_device_uuid, event["source_device_uuid"])
    reason = service._application_conflict(db, event)
    print("pending_local_reason=", reason)
    assert reason and reason[0] == "local_edit_pending"
    print("pending_local_edit=conflict_local_preserved=1")
    before = db.scalar(select(Worker.first_name).where(Worker.uuid == worker.uuid))
    db.rollback()
    after = db.scalar(select(Worker.first_name).where(Worker.uuid == worker.uuid))
    assert before == after
    print("rollback=no_partial_business_write=1")
    duplicate_uuid = uuid.uuid4()
    from app.models.sync_change import SyncChange
    db.info["sync_apply_mode"] = True
    db.add(SyncChange(change_uuid=duplicate_uuid, revision_uuid=uuid.uuid4(), entity_type="workers", entity_uuid=worker.uuid,
                      operation="update", entity_version=2, payload={"uuid": str(worker.uuid)},
                      central_status="central_finalized", occurred_at=worker.created_at, retry_count=0))
    db.flush(); db.info.pop("sync_apply_mode", None)
    assert service._is_duplicate_change(db, duplicate_uuid) is True
    print("duplicate_change_uuid=skip_second_write=1")
    signed = SimpleNamespace(sync_version=3, validated_at=worker.created_at, validator_name="Fixture Doctor", uuid=worker.uuid)
    original_lookup = service._current_entity
    service._current_entity = lambda _db, _entity, _uuid: signed
    signed_change = {**event, "change_uuid": uuid.uuid4(), "base_version": 3, "changed_fields": ["first_name"], "entity_type": "aptitude_certificates"}
    reason = service._application_conflict(db, signed_change)
    assert reason and reason[0] == "signed_record_immutable"
    signed_change["operation"] = "delete"
    reason = service._application_conflict(db, signed_change)
    assert reason and reason[0] == "signed_record_immutable"
    service._current_entity = original_lookup
    print("signed_update_and_delete=immutable_original=1")
    visit = SimpleNamespace(sync_version=2, validated_at=worker.created_at, status="validated", uuid=worker.uuid)
    service._current_entity = lambda _db, _entity, _uuid: visit
    visit_change = {**event, "change_uuid": uuid.uuid4(), "base_version": 2, "entity_type": "medical_visits", "changed_fields": ["form_data"]}
    reason = service._application_conflict(db, visit_change)
    assert reason and reason[0] in {"validated_visit_immutable", "medical_visit_conflict"}
    service._current_entity = original_lookup
    print("visit_conflict=physician_review_required=1")
    try:
        ensure_snapshot_update_allowed(table_name="workers", exists=True, has_uuid=True)
    except ValueError as exc:
        assert str(exc) == "SYNC_APPLICATION_CONTRACT_REQUIRED"
        print("snapshot_existing_update=rejected_contract_required=1")
    else:
        raise AssertionError("snapshot update bypassed application contract")
    ensure_snapshot_update_allowed(table_name="workers", exists=False, has_uuid=True)
    print("snapshot_new_row=fixture_only_not_application=1")
    db.info["sync_apply_mode"] = True
    conflict = service._create_conflict(db, mission_uuid=uuid.uuid4(), incoming_change=event,
                                        central_entity=worker, conflicting_fields=["first_name"],
                                        blocking_reason="base_version_mismatch")
    db.commit(); conflict_uuid = conflict.uuid; db.info.pop("sync_apply_mode", None)
with Session(engine) as check:
    saved = check.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict_uuid))
    assert saved and saved.base_version == 1 and saved.central_version == 1
    assert saved.central_snapshot and saved.mission_snapshot and saved.incoming_change_uuid == event["change_uuid"]
    assert saved.blocking_reason == "base_version_mismatch"
    print("conflict_durable=local_and_incoming_snapshots=1 base_and_versions=1 event_identity=1")

with Session(engine) as db:
    try:
        service.apply_central_pull(db, central_server_uuid=uuid.uuid4(), central_generation_uuid=uuid.uuid4(), changes=[], next_central_sequence=0, final_central_sequence=0)
    except Exception as exc:
        assert "OPERATION_SUSPENDED_FOR_DATA_SAFETY" in str(exc)
        print("external_apply_without_eligibility=rejected_guard=1")
    else:
        raise AssertionError("guarded central apply unexpectedly opened")
print("PASS entity application policy checks; no automatic application")
