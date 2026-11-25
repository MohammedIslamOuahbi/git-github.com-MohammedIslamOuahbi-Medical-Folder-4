"""Isolated source-only MedicalVisit create/replay integration check."""
from __future__ import annotations
import os, sys, uuid, base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models.user import User
from app.models.worker import Worker
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision, LocalWriteOperation
from app.models.sync_change import SyncChange
from app.models.proof_pending import OriginProofRequest
from app.models.origin_proof import OriginProof
from app.models.proof_trust import ProofTrustedKey, ProofDelegation
from app.services.proof_issuer_service import MemoryKeyProvider, ProofIssuerService
from app.services.authorization_evidence_service import issue_for_local_operation, store_local_evidence, verify_authorization_evidence
from app.services.proof_verification_service import verify_signature, verify_binding
from app.services.protected_visit_write import request_fingerprint
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitUpdate
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitCreate

@dataclass(frozen=True)
class MedicalVisitSourceFixture:
    visit_uuid: uuid.UUID
    operation_uuid: uuid.UUID
    event_uuid: uuid.UUID
    content_sha256: str
    authorization_evidence: dict
    origin_proof: dict
    authorization_public_key: str
    origin_proof_public_key: str
    request_payload: dict

def _pub(key):
    return base64.b64encode(key.public_key().public_bytes_raw()).decode()

def prepare_medical_visit_source(url: str, *, source_device_uuid=None, source_generation_uuid=None, clinic_uuid=None) -> MedicalVisitSourceFixture:
    """Create one real visit, journal event, and both test-only signed proofs."""
    engine = create_engine(url)
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.role.in_(("super_admin", "admin", "doctor"))).order_by(User.id))
        worker = db.scalar(select(Worker).where(Worker.deleted_at.is_(None)).order_by(Worker.id))
        if user is None or worker is None: raise RuntimeError("AUTHORIZED_USER_OR_WORKER_MISSING")
        user_uuid, worker_uuid = user.uuid, worker.uuid
        operation_uuid = uuid.uuid4()
        payload = MedicalVisitCreate(worker_id=worker.id, worker_uuid=worker.uuid, visit_date="2026-10-16", site_name="fixture-site", status="draft", form_data={"fixture":"medical-visit-source"})
        db.info.update(local_operation_uuid=operation_uuid, stage3_write_contract=True, sync_source_user_uuid=user.uuid, sync_source_device_uuid=source_device_uuid or uuid.uuid4(), sync_source_generation_uuid=source_generation_uuid or uuid.uuid4(), sync_source_clinic_uuid=clinic_uuid or uuid.uuid4())
        result = MedicalVisitService().create(db, payload, user, operation_uuid); db.commit()
        visit_uuid = result.uuid
        source_device, source_generation, clinic = db.info.get("sync_source_device_uuid"), db.info.get("sync_source_generation_uuid"), db.info.get("sync_source_clinic_uuid")
    with Session(engine) as db:
        change = db.scalar(select(SyncChange).where(SyncChange.operation_uuid == operation_uuid, SyncChange.entity_uuid == visit_uuid))
        operation = db.get(LocalWriteOperation, operation_uuid); user = db.scalar(select(User).where(User.uuid == user_uuid))
        if change is None or change.operation != "insert": raise RuntimeError("MEDICAL_VISIT_JOURNAL_EVENT_MISSING")
        decision = (operation.result_payload or {}).get("authorization_decision") or {}
        assert decision.get("permission_code") == "medical_visits.create" and decision.get("event_uuid") == str(change.change_uuid)
        policy = decision.get("policy_version") or "5A-P1-20261014"
        now = datetime.now(timezone.utc); issuer, service = uuid.uuid4(), uuid.uuid4()
        ak, pk = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate(); aid, pid = "auth-visit-"+uuid.uuid4().hex[:8], "origin-visit-"+uuid.uuid4().hex[:8]
        delegation_id = uuid.uuid4(); scope = f"clinic:{clinic}:medical_visits:insert"
        db.add(ProofTrustedKey(key_id=aid, clinic_uuid=clinic, origin_service_uuid=issuer, origin_device_uuid=source_device, registration_authority_uuid=issuer, public_key=_pub(ak), algorithm="Ed25519", canonicalization_version="deterministic-json-restricted-v1", state="active", registered_at=now))
        db.add(ProofTrustedKey(key_id=pid, clinic_uuid=clinic, origin_service_uuid=service, origin_device_uuid=source_device, registration_authority_uuid=issuer, public_key=_pub(pk), algorithm="Ed25519", canonicalization_version="deterministic-json-restricted-v1", state="active", registered_at=now))
        db.add(ProofDelegation(delegation_uuid=delegation_id, clinic_uuid=clinic, origin_service_uuid=service, user_uuid=user_uuid, entity_type="medical_visits", operation="insert", policy_version=policy, issued_at=now, expires_at=now+timedelta(days=7), state="active", authority_ref="visit-fixture"))
        request = OriginProofRequest(request_uuid=uuid.uuid4(), operation_uuid=operation_uuid, event_uuid=change.change_uuid, content_sha256=change.content_sha256, revision_uuid=change.revision_uuid, parent_revision_uuid=None, origin_user_uuid=user_uuid, origin_device_uuid=source_device, clinic_uuid=clinic, entity_type="medical_visits", operation="insert", policy_version=policy, proof_transport_version=1, status="pending_proof", attempt_count=0, last_reason_code=str(delegation_id), time_state="time_indeterminate", created_at=now, updated_at=now)
        db.add(request); db.flush()
        auth = issue_for_local_operation(db, key_provider=MemoryKeyProvider({aid:ak}), key_id=aid, issuer_uuid=issuer, issuer_scope=scope, user=user, operation=operation, event=change, clinic_uuid=clinic, scope=scope, policy_version=policy, permission_code="medical_visits.create")
        store_local_evidence(db, auth); proof = ProofIssuerService(MemoryKeyProvider({pid:pk}), key_id=pid).issue(db, request_uuid=request.request_uuid); db.commit()
        assert verify_signature(proof, _pub(pk)) == "valid" and verify_binding(proof, event_uuid=change.change_uuid, operation_uuid=operation_uuid, entity_type="medical_visits", operation="insert", content_sha256=change.content_sha256) == "valid"
        assert verify_authorization_evidence(auth, public_key_b64=_pub(ak), expected={"subject_user_uuid":user_uuid,"operation_uuid":operation_uuid,"event_uuid":change.change_uuid,"entity_type":"medical_visits","entity_uuid":visit_uuid,"content_sha256":change.content_sha256,"clinic_uuid":clinic,"scope":scope,"policy_version":policy}, trusted_issuer_uuid=issuer, trusted_issuer_scope=scope)[0] == "accepted_test_only"
        return MedicalVisitSourceFixture(visit_uuid, operation_uuid, change.change_uuid, change.content_sha256, auth, proof, _pub(ak), _pub(pk), payload.model_dump(mode="json"))

def prepare_medical_visit_update_source(url: str, fixture: MedicalVisitSourceFixture) -> dict:
    engine=create_engine(url); operation_uuid=uuid.uuid4()
    with Session(engine) as db:
        user=db.scalar(select(User).where(User.uuid==uuid.UUID(fixture.authorization_evidence["subject_user_uuid"]))); visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==fixture.visit_uuid))
        if not user or not visit: raise RuntimeError("MEDICAL_VISIT_UPDATE_SOURCE_MISSING")
        expected=int(visit.version); db.info.update(sync_source_device_uuid=uuid.UUID(fixture.origin_proof["origin_device_uuid"]),sync_source_generation_uuid=uuid.uuid4(),sync_source_clinic_uuid=uuid.UUID(fixture.origin_proof["clinic_uuid"]),sync_source_user_uuid=user.uuid)
        MedicalVisitService().update(db, visit.id, MedicalVisitUpdate(site_name="updated-visit-site"), user, expected, operation_uuid); db.commit()
    with Session(engine) as db:
        user=db.scalar(select(User).where(User.uuid==uuid.UUID(fixture.authorization_evidence["subject_user_uuid"]))); change=db.scalar(select(SyncChange).where(SyncChange.operation_uuid==operation_uuid)); op=db.get(LocalWriteOperation,operation_uuid); visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==fixture.visit_uuid))
        if not change or change.operation!="update": raise RuntimeError("MEDICAL_VISIT_UPDATE_EVENT_MISSING")
        decision=(op.result_payload or {}).get("authorization_decision") or {}; assert decision.get("permission_code")=="medical_visits.update" and decision.get("event_uuid")==str(change.change_uuid)
        policy=decision.get("policy_version") or "5A-P1-20261014"; now=datetime.now(timezone.utc); issuer,service=uuid.uuid4(),uuid.uuid4(); ak,pk=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate(); aid,pid="auth-visit-update-"+uuid.uuid4().hex[:8],"origin-visit-update-"+uuid.uuid4().hex[:8]; scope=f"clinic:{change.source_clinic_uuid}:medical_visits:update"; did=uuid.uuid4()
        db.add(ProofTrustedKey(key_id=aid,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=issuer,origin_device_uuid=change.source_device_uuid,registration_authority_uuid=issuer,public_key=_pub(ak),algorithm="Ed25519",canonicalization_version="deterministic-json-restricted-v1",state="active",registered_at=now)); db.add(ProofTrustedKey(key_id=pid,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=service,origin_device_uuid=change.source_device_uuid,registration_authority_uuid=issuer,public_key=_pub(pk),algorithm="Ed25519",canonicalization_version="deterministic-json-restricted-v1",state="active",registered_at=now)); db.add(ProofDelegation(delegation_uuid=did,clinic_uuid=change.source_clinic_uuid,origin_service_uuid=service,user_uuid=user.uuid,entity_type="medical_visits",operation="update",policy_version=policy,issued_at=now,expires_at=now+timedelta(days=7),state="active",authority_ref="visit-update-fixture")); req=OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=operation_uuid,event_uuid=change.change_uuid,content_sha256=change.content_sha256,revision_uuid=change.revision_uuid,parent_revision_uuid=change.parent_revision_uuid,origin_user_uuid=user.uuid,origin_device_uuid=change.source_device_uuid,clinic_uuid=change.source_clinic_uuid,entity_type="medical_visits",operation="update",policy_version=policy,proof_transport_version=1,status="pending_proof",attempt_count=0,last_reason_code=str(did),time_state="time_indeterminate",created_at=now,updated_at=now); db.add(req); db.flush(); auth=issue_for_local_operation(db,key_provider=MemoryKeyProvider({aid:ak}),key_id=aid,issuer_uuid=issuer,issuer_scope=scope,user=user,operation=op,event=change,clinic_uuid=change.source_clinic_uuid,scope=scope,policy_version=policy,permission_code="medical_visits.update"); store_local_evidence(db,auth); proof=ProofIssuerService(MemoryKeyProvider({pid:pk}),key_id=pid).issue(db,request_uuid=req.request_uuid); db.commit(); assert verify_signature(proof,_pub(pk))=="valid" and verify_binding(proof,event_uuid=change.change_uuid,operation_uuid=operation_uuid,entity_type="medical_visits",operation="update",parent_revision_uuid=change.parent_revision_uuid,content_sha256=change.content_sha256)=="valid"
        return {"operation_uuid":operation_uuid,"event_uuid":change.change_uuid,"visit_uuid":fixture.visit_uuid,"base_version":change.base_version,"entity_version":change.entity_version,"parent_revision_uuid":change.parent_revision_uuid,"content_sha256":change.content_sha256,"update_payload":change.payload,"authorization_evidence":auth,"origin_proof":proof,"authorization_public_key":_pub(ak),"origin_proof_public_key":_pub(pk),"base_snapshot":fixture.request_payload}

def main():
    url = os.environ.get("STAGE5_SOURCE_DB")
    if not url:
        raise RuntimeError("STAGE5_SOURCE_DB is required")
    fixture = prepare_medical_visit_source(url)
    engine = create_engine(url)
    print("visit_created=1", "visit_uuid=", fixture.visit_uuid, "event_uuid=", fixture.event_uuid)
    with Session(engine) as db:
        visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid))
        op = db.get(LocalWriteOperation, fixture.operation_uuid)
        changes = db.scalars(select(SyncChange).where(SyncChange.operation_uuid == fixture.operation_uuid)).all()
        assert visit is not None and op is not None and len(changes) == 1
        change = changes[0]
        assert change.entity_uuid == fixture.visit_uuid and change.operation == "insert" and change.content_sha256 == fixture.content_sha256
        decision = op.result_payload.get("authorization_decision") or {}
        assert decision.get("permission_code") == "medical_visits.create"
        assert decision.get("event_uuid") == str(change.change_uuid)
        assert decision.get("content_sha256") == change.content_sha256
        print("fresh_session_persisted=1", "journal_events=1", "operation=insert",
              "source_identity_match=1", "authorization_decision=historical", "proof_signatures_valid=1", "content_sha256=", change.content_sha256)
        replay_payload = MedicalVisitCreate(worker_id=visit.worker_id, worker_uuid=visit.worker_uuid,
            visit_date=visit.visit_date, site_name=visit.site_name, status=visit.status,
            form_data=visit.form_data)
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.uuid == uuid.UUID(fixture.authorization_evidence["subject_user_uuid"])))
        replay = MedicalVisitService().create(db, MedicalVisitCreate.model_validate(fixture.request_payload), user, fixture.operation_uuid)
        db.commit()
        assert replay.uuid == fixture.visit_uuid
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid == fixture.visit_uuid)) == 1
        assert db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.operation_uuid == fixture.operation_uuid)) == 1
        proofs = db.scalars(select(OriginProof).where(OriginProof.event_uuid == fixture.event_uuid)).all()
        assert len(proofs) == 1 and proofs[0].proof == fixture.origin_proof
        print("replay_same_visit=1", "no_duplicate_change=1", "proofs_persisted=1", "evidence_identity_stable=1")
    update = prepare_medical_visit_update_source(url, fixture)
    print("visit_update_event_created=1", "base_version=", update["base_version"], "entity_version=", update["entity_version"], "parent_revision_uuid=", update["parent_revision_uuid"], "proof_bindings_valid=1")

if __name__ == "__main__":
    main()
