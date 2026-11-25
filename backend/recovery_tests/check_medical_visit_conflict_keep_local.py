"""Isolated physician_review -> keep_local conflict-resolution check."""
from __future__ import annotations
import os, sys, uuid
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.models.medical_visit import MedicalVisit
from app.models.sync_conflict import SyncConflict
from app.models.audit_log import AuditLog
from app.models.local_revision import LocalRevision
from app.models.local_revision import LocalWriteOperation
from app.models.sync_change import SyncChange
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.permission_service import permission_service
from app.services.central_sync_service import CentralSyncService
from app.services.entity_application_service import apply_medical_visit_entity, apply_medical_visit_update_entity
from recovery_tests.check_medical_visit_source_fixture import prepare_medical_visit_source, prepare_medical_visit_update_source
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitUpdate
from app.schemas.permission import UserPermissionUpdateRequest, PermissionOverrideUpdateItem

def ev(**kw): return type("Incoming", (), kw)()

@dataclass(frozen=True)
class UnresolvedVisitConflict:
    visit_uuid: uuid.UUID
    conflict_uuid: uuid.UUID
    incoming_event_uuid: uuid.UUID
    reviewer_user_uuid: uuid.UUID
    snapshot_before_resolution: dict

def prepare_unresolved_visit_conflict(source_url: str, target_url: str) -> UnresolvedVisitConflict:
    src=prepare_medical_visit_source(source_url); upd=prepare_medical_visit_update_source(source_url,src); te=create_engine(target_url)
    with Session(te) as db:
        from app.models.worker import Worker
        if db.scalar(select(Worker).where(Worker.uuid==uuid.UUID(str(src.request_payload["worker_uuid"])))) is None: raise RuntimeError("TARGET_WORKER_DEPENDENCY_MISSING")
        base=ev(event_uuid=src.event_uuid,operation_uuid=src.operation_uuid,entity_uuid=src.visit_uuid,revision_uuid=uuid.UUID(str(src.origin_proof["revision_uuid"])),payload=src.request_payload); assert apply_medical_visit_entity(db,base)["status"]=="applied"; db.commit()
        user=db.scalar(select(User).where(User.role == "doctor").order_by(User.id))
        if user is None or "medical_visits.update" not in permission_service.get_effective_permission_codes(user) or "sync.resolve_conflicts" not in permission_service.get_effective_permission_codes(user):
            db.info["sync_bootstrap_mode"]=True; user=AuthService().create_platform_user(db,"Conflict","Doctor","conflict-doctor-"+uuid.uuid4().hex[:8]+"@test.local","test-only","doctor"); db.commit(); db.info.pop("sync_bootstrap_mode",None)
            actor=next((candidate for candidate in db.scalars(select(User).where(User.role.in_(("super_admin","admin"))).order_by(User.id)) if "users.edit_permissions" in permission_service.get_effective_permission_codes(candidate)), None)
            if actor is None: raise RuntimeError("PERMISSION_ADMIN_MISSING")
            permission_op=uuid.uuid4(); db.add(LocalWriteOperation(operation_uuid=permission_op,actor_user_uuid=actor.uuid,request_hash="permission-fixture",entity_type="users",entity_uuid=user.uuid,result_payload={},created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush(); db.info.update(local_operation_uuid=permission_op,stage3_write_contract=True)
            permission_service.update_user_permissions(db,user.id,UserPermissionUpdateRequest(permissions=[PermissionOverrideUpdateItem(permission_code="sync.resolve_conflicts",state="allow"),PermissionOverrideUpdateItem(permission_code="medical_visits.update",state="allow")],reason="fixture"),actor,None,None); db.commit(); db.info.pop("local_operation_uuid",None); db.info.pop("stage3_write_contract",None)
        permission_service.require_permission(user,"medical_visits.update"); permission_service.require_permission(user,"sync.resolve_conflicts")
        visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==src.visit_uuid)); db.info.update(sync_source_device_uuid=uuid.uuid4(),sync_source_generation_uuid=uuid.uuid4(),sync_source_clinic_uuid=uuid.uuid4(),sync_source_user_uuid=user.uuid); MedicalVisitService().update(db,visit.id,MedicalVisitUpdate(site_name="local-keep"),user,1,uuid.uuid4()); db.commit(); reviewer=user.uuid
    with Session(te) as db:
        incoming=ev(event_uuid=upd["event_uuid"],operation_uuid=upd["operation_uuid"],entity_uuid=src.visit_uuid,revision_uuid=uuid.UUID(str(upd["origin_proof"]["revision_uuid"])),parent_revision_uuid=upd["parent_revision_uuid"],base_version=1,payload=upd["update_payload"])
        assert apply_medical_visit_update_entity(db,incoming)["status"]=="conflict"
        if db.scalar(select(SyncChange).where(SyncChange.change_uuid == uuid.UUID(str(upd["event_uuid"])))) is None:
            db.add(SyncChange(change_uuid=uuid.UUID(str(upd["event_uuid"])), revision_uuid=incoming.revision_uuid,
                              operation_uuid=incoming.operation_uuid, entity_type="medical_visits",
                              entity_uuid=incoming.entity_uuid, operation="update", base_version=1,
                              entity_version=2, parent_revision_uuid=incoming.parent_revision_uuid,
                              payload=dict(incoming.payload), content_sha256=upd.get("content_sha256"),
                              occurred_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
                              central_status="central_pending", retry_count=0))
        db.commit(); conflict=db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid==upd["event_uuid"]))
        if conflict is None or conflict.status!="physician_review": raise AssertionError("UNRESOLVED_CONFLICT_MISSING")
        return UnresolvedVisitConflict(src.visit_uuid,conflict.uuid,upd["event_uuid"],reviewer,dict(conflict.central_snapshot or {}))

def run_doctor_without_resolve_permission(source_url: str, target_url: str) -> None:
    fixture = prepare_unresolved_visit_conflict(source_url, target_url)
    engine = create_engine(target_url)
    with Session(engine) as db:
        actor = next((candidate for candidate in db.scalars(select(User).order_by(User.id))
                      if "users.edit_permissions" in permission_service.get_effective_permission_codes(candidate)), None)
        if actor is None:
            raise RuntimeError("PERMISSION_ADMIN_MISSING")
        account_op=uuid.uuid4(); db.add(LocalWriteOperation(operation_uuid=account_op,actor_user_uuid=actor.uuid,request_hash="doctor-account-fixture",entity_type="users",entity_uuid=uuid.uuid4(),result_payload={},created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush(); db.info.update(local_operation_uuid=account_op,stage3_write_contract=True)
        doctor = AuthService().create_platform_user(
            db, "Review", "Doctor", "review-denied-" + uuid.uuid4().hex[:8] + "@test.local", "test-only", "doctor")
        db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)
        db.flush()
        op_uuid = uuid.uuid4()
        db.add(LocalWriteOperation(operation_uuid=op_uuid, actor_user_uuid=actor.uuid,
                                   request_hash="permission-deny-fixture", entity_type="users",
                                   entity_uuid=doctor.uuid, result_payload={},
                                   created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
        db.flush(); db.info.update(local_operation_uuid=op_uuid, stage3_write_contract=True)
        permission_service.update_user_permissions(
            db, doctor.id,
            UserPermissionUpdateRequest(permissions=[
                PermissionOverrideUpdateItem(permission_code="medical_visits.update", state="allow"),
                PermissionOverrideUpdateItem(permission_code="sync.resolve_conflicts", state="deny"),
            ], reason="keep-local denial fixture"), actor, None, None)
        db.commit(); db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)
        db.refresh(doctor)
        assert "medical_visits.update" in permission_service.get_effective_permission_codes(doctor)
        assert "sync.resolve_conflicts" not in permission_service.get_effective_permission_codes(doctor)
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        before_audit = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        try:
            CentralSyncService().resolve_conflict(db, fixture.conflict_uuid, resolution_type="keep_local",
                                                  resolved_payload=None, current_user=doctor,
                                                  resolution_reason="denied-doctor")
        except Exception as exc:
            assert "Insufficient permissions" in str(exc)
            db.rollback()
            print("doctor_without_permission=rejected")
        else:
            raise AssertionError("doctor without sync.resolve_conflicts was accepted")
    with Session(engine) as check:
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        audit_count = check.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        assert conflict.status == "physician_review" and conflict.resolved_payload is None
        assert conflict.resolved_by_user_uuid is None and conflict.resolved_at is None
        assert audit_count == before_audit
        assert visit is not None and visit.site_name == "local-keep"
        print("conflict_unresolved=1", "resolution_audit_added=0", "local_and_evidence_preserved=1")

def run_admin_without_physician_eligibility(source_url: str, target_url: str) -> None:
    fixture = prepare_unresolved_visit_conflict(source_url, target_url)
    engine = create_engine(target_url)
    with Session(engine) as db:
        admin = next((candidate for candidate in db.scalars(select(User).where(User.role == "admin").order_by(User.id))
                      if "sync.resolve_conflicts" in permission_service.get_effective_permission_codes(candidate)), None)
        if admin is None:
            raise RuntimeError("ADMIN_SYNC_RESOLVE_PERMISSION_MISSING")
        assert "sync.resolve_conflicts" in permission_service.get_effective_permission_codes(admin)
        assert (admin.role or "").strip().lower() != "doctor"
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        audit_before = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        try:
            CentralSyncService().resolve_conflict(db, fixture.conflict_uuid, resolution_type="keep_local",
                                                  resolved_payload=None, current_user=admin,
                                                  resolution_reason="admin-not-physician")
        except Exception as exc:
            assert "PHYSICIAN_REVIEW_REQUIRES_AUTHORIZED_VALIDATOR" in str(exc)
            db.rollback()
            print("admin_with_permission=rejected")
            print("admin_not_physician=eligibility_rejected")
        else:
            raise AssertionError("non-physician admin was accepted")
    with Session(engine) as check:
        conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        audit_after = check.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        assert conflict.status == "physician_review" and conflict.resolved_payload is None
        assert conflict.resolved_by_user_uuid is None and conflict.resolved_at is None and audit_after == audit_before
        assert visit is not None and visit.site_name == "local-keep"
        print("conflict_unresolved=1", "resolution_audit_added=0", "local_and_evidence_preserved=1")

def run_version_changed_keep_local(source_url: str, target_url: str) -> None:
    """A post-conflict local update must prevent keep_local resolution."""
    fixture = prepare_unresolved_visit_conflict(source_url, target_url)
    engine = create_engine(target_url)
    with Session(engine) as db:
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        assert conflict is not None and visit is not None and conflict.status == "physician_review"
        snapshot_version = conflict.central_version
        before_local_changes = db.scalar(
            select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == fixture.visit_uuid)
        ) or 0
        reviewer = db.scalar(select(User).where(User.uuid == fixture.reviewer_user_uuid))
        assert reviewer is not None
        permission_service.require_permission(reviewer, "medical_visits.update")
        current_version = getattr(visit, "version", None)
        if current_version is None:
            current_version = getattr(visit, "sync_version", None)
        assert current_version is not None and snapshot_version is not None
        db.info.update(
            sync_source_device_uuid=uuid.uuid4(),
            sync_source_generation_uuid=uuid.uuid4(),
            sync_source_clinic_uuid=uuid.uuid4(),
            sync_source_user_uuid=reviewer.uuid,
        )
        MedicalVisitService().update(
            db,
            visit.id,
            MedicalVisitUpdate(site_name="version-changed-local"),
            reviewer,
            int(current_version),
            uuid.uuid4(),
        )
        db.commit()
    with Session(engine) as check:
        visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        reviewer = check.scalar(select(User).where(User.uuid == fixture.reviewer_user_uuid))
        assert reviewer is not None
        changed_version = getattr(visit, "version", None)
        if changed_version is None:
            changed_version = getattr(visit, "sync_version", None)
        assert changed_version != snapshot_version
        assert conflict.central_version == snapshot_version
        print("version_changed=1", f"conflict_snapshot_version={snapshot_version}", f"visit_version={changed_version}")
        audit_before = check.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)
        ) or 0
        changes_before_resolution = check.scalar(
            select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == fixture.visit_uuid)
        ) or 0
        try:
            CentralSyncService().resolve_conflict(
                check,
                fixture.conflict_uuid,
                resolution_type="keep_local",
                resolved_payload=None,
                current_user=reviewer,
                resolution_reason="version-changed",
            )
        except Exception as exc:
            assert "CONFLICT_VERSION_CHANGED" in str(exc)
            check.rollback()
            print("keep_local_version_changed=rejected")
        else:
            raise AssertionError("keep_local accepted a changed visit version")
    with Session(engine) as final:
        conflict = final.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        visit = final.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        audit_after = final.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        changes_after = final.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == fixture.visit_uuid)) or 0
        assert conflict.status == "physician_review"
        assert conflict.resolved_payload is None and conflict.resolved_by_user_uuid is None and conflict.resolved_at is None
        assert audit_after == audit_before and changes_after == changes_before_resolution
        assert visit.site_name == "version-changed-local"
        print("conflict_unresolved=1", "resolution_audit_added=0", "local_update_preserved=1", "sync_changes_unchanged=1")

def run_keep_local_rollback(source_url: str, target_url: str) -> None:
    """Injected failure after conflict/audit writes must roll back atomically."""
    fixture = prepare_unresolved_visit_conflict(source_url, target_url)
    engine = create_engine(target_url)
    with Session(engine) as db:
        conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        reviewer = db.scalar(select(User).where(User.uuid == fixture.reviewer_user_uuid))
        assert conflict is not None and visit is not None and reviewer is not None
        before = {
            "status": conflict.status,
            "payload": conflict.resolved_payload,
            "by": conflict.resolved_by_user_uuid,
            "at": conflict.resolved_at,
            "site": visit.site_name,
            "audit": db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0,
            "changes": db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == fixture.visit_uuid)) or 0,
        }
        db.info["inject_keep_local_failure"] = True
        try:
            CentralSyncService().resolve_conflict(
                db, fixture.conflict_uuid, resolution_type="keep_local", resolved_payload=None,
                current_user=reviewer, resolution_reason="rollback-keep-local",
            )
        except Exception as exc:
            assert "INJECTED_KEEP_LOCAL_FAILURE_BEFORE_COMMIT" in str(exc)
            db.rollback()
            print("keep_local_injected_failure=reached")
        else:
            raise AssertionError("keep_local failure injection did not fire")
        finally:
            db.info.pop("inject_keep_local_failure", None)
    with Session(engine) as check:
        conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        audit = check.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        changes = check.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == fixture.visit_uuid)) or 0
        assert conflict.status == before["status"] == "physician_review"
        assert conflict.resolved_payload == before["payload"] is None
        assert conflict.resolved_by_user_uuid == before["by"] is None and conflict.resolved_at == before["at"] is None
        assert audit == before["audit"] and changes == before["changes"]
        assert visit.site_name == before["site"]
        print("rollback_persisted=1", "conflict_unresolved=1", "resolution_audit_added=0", "visit_and_evidence_preserved=1")
    with Session(engine) as db:
        reviewer = db.scalar(select(User).where(User.uuid == fixture.reviewer_user_uuid))
        resolved = CentralSyncService().resolve_conflict(
            db, fixture.conflict_uuid, resolution_type="keep_local", resolved_payload=None,
            current_user=reviewer, resolution_reason="rollback-keep-local",
        )
        assert resolved.status == "resolved"
    with Session(engine) as check:
        conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture.conflict_uuid))
        audit_after = check.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        assert conflict.status == "resolved" and audit_after == before["audit"] + 1
        reviewer = check.scalar(select(User).where(User.uuid == fixture.reviewer_user_uuid))
        assert CentralSyncService().resolve_conflict(
            check, fixture.conflict_uuid, resolution_type="keep_local", resolved_payload=None,
            current_user=reviewer, resolution_reason="rollback-keep-local",
        ).status == "resolved"
        audit_replay = check.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == conflict.id)) or 0
        assert audit_replay == audit_after
        print("retry_keep_local=resolved", "audit_count=1", "replay_audit_unchanged=1")

def main():
    s=os.environ["STAGE5_SOURCE_DB"]; t=os.environ["STAGE5_TARGET_DB"]; te=create_engine(t)
    run_doctor_without_resolve_permission(s, t)
    run_admin_without_physician_eligibility(s, t)
    run_version_changed_keep_local(s, t)
    run_keep_local_rollback(s, t)
    prepared=prepare_unresolved_visit_conflict(s,t)
    print("unresolved_fixture=", str(prepared.conflict_uuid), "status=physician_review")
    src=prepare_medical_visit_source(s); upd=prepare_medical_visit_update_source(s,src)
    with Session(te) as db:
        from app.models.worker import Worker
        if db.scalar(select(Worker).where(Worker.uuid==uuid.UUID(str(src.request_payload["worker_uuid"])))) is None: raise RuntimeError("TARGET_WORKER_DEPENDENCY_MISSING")
        base=ev(event_uuid=src.event_uuid,operation_uuid=src.operation_uuid,entity_uuid=src.visit_uuid,revision_uuid=uuid.UUID(str(src.origin_proof["revision_uuid"])),payload=src.request_payload)
        assert apply_medical_visit_entity(db,base)["status"]=="applied"; db.commit()
        user=db.scalar(select(User).where(User.role == "doctor").order_by(User.id))
        if user is None or "medical_visits.update" not in permission_service.get_effective_permission_codes(user) or "sync.resolve_conflicts" not in permission_service.get_effective_permission_codes(user):
            db.info["sync_bootstrap_mode"]=True; user=AuthService().create_platform_user(db,"Conflict","Doctor","conflict-doctor-"+uuid.uuid4().hex[:8]+"@test.local","test-only","doctor"); db.commit(); db.info.pop("sync_bootstrap_mode",None)
            actor=next((candidate for candidate in db.scalars(select(User).where(User.role.in_(("super_admin","admin"))).order_by(User.id)) if "users.edit_permissions" in permission_service.get_effective_permission_codes(candidate)), None)
            if actor is None: raise RuntimeError("PERMISSION_ADMIN_MISSING")
            permission_op=uuid.uuid4(); db.add(LocalWriteOperation(operation_uuid=permission_op,actor_user_uuid=actor.uuid,request_hash="permission-fixture",entity_type="users",entity_uuid=user.uuid,result_payload={},created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush(); db.info.update(local_operation_uuid=permission_op,stage3_write_contract=True)
            permission_service.update_user_permissions(db,user.id,UserPermissionUpdateRequest(permissions=[PermissionOverrideUpdateItem(permission_code="sync.resolve_conflicts",state="allow"),PermissionOverrideUpdateItem(permission_code="medical_visits.update",state="allow")],reason="fixture"),actor,None,None); db.commit()
            db.info.pop("local_operation_uuid",None); db.info.pop("stage3_write_contract",None)
        permission_service.require_permission(user,"medical_visits.update"); permission_service.require_permission(user,"sync.resolve_conflicts")
        visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==src.visit_uuid)); db.info.update(sync_source_device_uuid=uuid.uuid4(),sync_source_generation_uuid=uuid.uuid4(),sync_source_clinic_uuid=uuid.uuid4(),sync_source_user_uuid=user.uuid)
        MedicalVisitService().update(db,visit.id,MedicalVisitUpdate(site_name="local-keep"),user,1,uuid.uuid4()); db.commit()
        user_uuid=user.uuid
    with Session(te) as db:
        incoming=ev(event_uuid=upd["event_uuid"],operation_uuid=upd["operation_uuid"],entity_uuid=src.visit_uuid,revision_uuid=uuid.UUID(str(upd["origin_proof"]["revision_uuid"])),parent_revision_uuid=upd["parent_revision_uuid"],base_version=1,payload=upd["update_payload"])
        assert apply_medical_visit_update_entity(db,incoming)["status"]=="conflict"; db.commit()
        conflict=db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid==upd["event_uuid"]))
        if conflict is None: raise AssertionError("CONFLICT_NOT_CREATED")
        cid=conflict.uuid; conflict_id=conflict.id; entity_uuid=conflict.entity_uuid; before_changes=db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid==entity_uuid))
        user=db.scalar(select(User).where(User.uuid==user_uuid))
        resolved=CentralSyncService().resolve_conflict(db,cid,resolution_type="keep_local",resolved_payload=None,current_user=user,resolution_reason="physician_review_keep_local")
        assert resolved.status=="resolved" and resolved.resolution_type=="keep_local"
        db.commit()
    with Session(te) as db:
        row=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==entity_uuid)); c=db.get(SyncConflict,conflict_id); audits=db.scalars(select(AuditLog).where(AuditLog.entity_type=="sync_conflicts",AuditLog.entity_id==c.id)).all(); changes=db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid==entity_uuid))
        assert row.site_name=="local-keep" and c.status=="resolved" and audits and changes==before_changes and (c.resolved_payload or {}).get("resolution_reason")=="physician_review_keep_local"
        print("keep_local=resolved physician_review=1 local_preserved=1 audit_durable=1 incoming_sync_changes=0")
        replay_user=db.scalar(select(User).where(User.uuid==user_uuid))
        assert CentralSyncService().resolve_conflict(db,cid,resolution_type="keep_local",resolved_payload=None,current_user=replay_user,resolution_reason="physician_review_keep_local").status=="resolved"
        print("replay=idempotent=1")
        try:
            CentralSyncService().resolve_conflict(db,cid,resolution_type="keep_local",resolved_payload=None,current_user=replay_user,resolution_reason="different-reason")
        except Exception as exc:
            assert "RESOLUTION_IDENTITY_REUSED_WITH_DIFFERENT_CONTENT" in str(exc)
            print("same_identity_different_reason=rejected=1")
        else:
            raise AssertionError("resolution identity reuse was accepted")
        print("audit_count_stable=1", "conflict_status=resolved", "visit_and_evidence_unchanged=1")

if __name__=="__main__": main()
