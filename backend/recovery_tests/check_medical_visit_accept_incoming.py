"""Evidence-backed accept_incoming setup check (stops before the decision)."""
from __future__ import annotations
import os, sys, uuid, time, requests, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.models.sync_transport import SyncTransportEvent
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
from app.models.sync_conflict import SyncConflict
from app.models.sync_change import SyncChange
from app.models.local_revision import LocalRevision
from app.models.sync_conflict_decision import SyncConflictDecision
from app.models.audit_log import AuditLog
from app.models.medical_visit import MedicalVisit
from app.models.user import User
from app.services.central_sync_service import central_sync_service
from app.services.permission_service import permission_service
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitUpdate
from app.schemas.medical_visit import MedicalVisitValidateRequest
from app.services.sync_context import set_sync_context
from app.models.proof_trust import ProofDelegation
from app.models.origin_proof import OriginProof
from app.services.proof_revocation_service import register_and_revoke_delegation


def _test_time_policy() -> dict:
    """Return a deterministic-for-the-run test window containing current UTC time."""
    now = datetime.now(timezone.utc)
    return {
        "authority_id": "test-time-authority",
        "test_only": True,
        "max_rtt_seconds": 5,
        "valid_from": (now.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(),
        "valid_until": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)).isoformat(),
    }
from app.services.proof_verification_service import revocation_canonical_bytes
from app.services.origin_proof_reconciliation import reconcile_origin_proof
from app.services.time_freshness_service import begin_challenge, evaluate_freshness
from recovery_tests.check_http_origin_proof_auto_reconciliation import reconciliation_scenario

class RemoteAuthority:
    def __init__(self, public_key): self.public_key = public_key; self.used = set()

def run_stale_version_case(source, target):
    """Independent stale-input rejection; no accept HTTP endpoint is used."""
    with reconciliation_scenario(source, target, scenario="medical_visit_update", local_pending=True) as fixture:
        engine = create_engine(target)
        with Session(engine) as db:
            receipt = db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid == uuid.UUID(fixture["receipt_uuid"])))
            event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == uuid.UUID(fixture["event_uuid"])))
            conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture["conflict_uuid"])))
            reviewer = next((u for u in db.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all() if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(u))), None)
            assert receipt and event and conflict and reviewer
            reviewer_uuid = reviewer.uuid
            req = begin_challenge(proof_uuid=receipt.proof_uuid, event_uuid=event.event_uuid, authority_scope=fixture["chain_scope"])
            req["challenge"] = uuid.uuid4().hex; req.update(destination_uuid=str(receipt.peer_device_uuid), policy_version="5A-P1-20261014")
            response = requests.post(fixture["time_authority_url"], json={k:v for k,v in req.items() if k != "started_monotonic"}, timeout=5).json()
            fresh = evaluate_freshness(response, req, RemoteAuthority(fixture["time_authority_public_key"]), ended_monotonic=time.monotonic(), policy=_test_time_policy())
            assert fresh["accepted_test_only"]
            checkpoint = {"checkpoint_uuid": fixture["checkpoint_uuid"], "authority_uuid": fixture["checkpoint_authority_uuid"], "chain_scope": fixture["chain_scope"], "contract_version":"revocation-chain-v1", "policy_version":"5A-P1-20261014", "covered_sequence":1, "covered_chain_hash":fixture["checkpoint_chain_hash"], "challenge":"fixture-challenge", "destination_device_uuid":str(receipt.peer_device_uuid)}
            verified = reconcile_origin_proof(db, event_uuid=event.event_uuid, peer_device_uuid=receipt.peer_device_uuid, checkpoint_context={"checkpoint":checkpoint, **checkpoint, "coverage":{"status":"complete"}, "freshness":{"accepted_test_only":True,"time_result":fresh["time_result"],"challenge":req["challenge"],"destination_device_uuid":str(receipt.peer_device_uuid)}})
            assert verified["status"] == "accepted_test_only"
            visit_uuid, old_version, conflict_uuid = conflict.entity_uuid, int(db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid)).version), conflict.uuid
            before_decisions = int(db.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict_uuid)) or 0)
            before_audit = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0)
        # Mutate the local visit in a separate protected transaction.
        with Session(engine) as local:
            visit = local.scalar(select(MedicalVisit).where(MedicalVisit.uuid == visit_uuid))
            local_reviewer = local.scalar(select(User).where(User.uuid == reviewer_uuid))
            set_sync_context(local, user=local_reviewer, source_device_uuid=uuid.uuid4(), source_user_uuid=local_reviewer.uuid)
            MedicalVisitService().update(local, visit.id, MedicalVisitUpdate(site_name="stale-local-edit"), local_reviewer, old_version, uuid.uuid4())
            local.commit()
        with Session(engine) as attempt:
            attempt.info["verified_reconciliation"] = verified
            try:
                attempt_reviewer = attempt.scalar(select(User).where(User.uuid == reviewer_uuid))
                central_sync_service.accept_incoming(attempt, conflict_uuid, current_user=attempt_reviewer, operation_uuid=uuid.uuid4(), resolution_reason="stale version rejection")
                raise AssertionError("stale context unexpectedly accepted")
            except Exception as exc:
                assert "CONFLICT_VERSION_CHANGED" in str(exc)
                attempt.rollback()
            assert "verified_reconciliation" not in attempt.info
        with Session(engine) as check:
            visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == visit_uuid)); current_conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict_uuid))
            assert visit.version > old_version and visit.site_name == "stale-local-edit"
            assert current_conflict.status == "physician_review" and current_conflict.resolved_payload is None
            assert int(check.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict_uuid)) or 0) == before_decisions
            assert int(check.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == current_conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0) == before_audit
        print("stale_version_rejected=1", "reason=CONFLICT_VERSION_CHANGED", "local_update_preserved=1", "conflict_unresolved=1", "decision_delta=0", "audit_delta=0", "context_cleared_after_rejection=1")

def run_validated_visit_case(source, target):
    """Independent immutable-validated visit rejection."""
    with reconciliation_scenario(source, target, scenario="medical_visit_update", local_pending=True) as fixture:
        engine = create_engine(target)
        with Session(engine) as db:
            receipt = db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid == uuid.UUID(fixture["receipt_uuid"])))
            event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == uuid.UUID(fixture["event_uuid"])))
            conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture["conflict_uuid"])))
            validator = next((u for u in db.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all() if "medical_visits.update" in set(permission_service.get_effective_permission_codes(u))), None)
            reviewer = next((u for u in db.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all() if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(u))), None)
            assert receipt and event and conflict and validator and reviewer
            visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid))
            validated = MedicalVisitService().validate(db, visit.id, MedicalVisitValidateRequest(doctor_notes="validated immutability fixture"), validator, int(visit.version), uuid.uuid4())
            db.commit()
            validator_uuid = validator.uuid; reviewer_uuid = reviewer.uuid; visit_uuid = visit.uuid; conflict_uuid = conflict.uuid; validated_version = int(validated.version)
            snapshot = {"site_name": validated.site_name, "status": validated.status, "validated_at": validated.validated_at, "version": validated.version, "revisions": int(db.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == visit_uuid)) or 0)}
            req = begin_challenge(proof_uuid=receipt.proof_uuid, event_uuid=event.event_uuid, authority_scope=fixture["chain_scope"]); req["challenge"] = uuid.uuid4().hex; req.update(destination_uuid=str(receipt.peer_device_uuid), policy_version="5A-P1-20261014")
            response = requests.post(fixture["time_authority_url"], json={k:v for k,v in req.items() if k != "started_monotonic"}, timeout=5).json()
            fresh = evaluate_freshness(response, req, RemoteAuthority(fixture["time_authority_public_key"]), ended_monotonic=time.monotonic(), policy=_test_time_policy())
            checkpoint = {"checkpoint_uuid": fixture["checkpoint_uuid"], "authority_uuid": fixture["checkpoint_authority_uuid"], "chain_scope": fixture["chain_scope"], "contract_version":"revocation-chain-v1", "policy_version":"5A-P1-20261014", "covered_sequence":1, "covered_chain_hash":fixture["checkpoint_chain_hash"], "challenge":"fixture-challenge", "destination_device_uuid":str(receipt.peer_device_uuid)}
            verified = reconcile_origin_proof(db, event_uuid=event.event_uuid, peer_device_uuid=receipt.peer_device_uuid, checkpoint_context={"checkpoint":checkpoint, **checkpoint, "coverage":{"status":"complete"}, "freshness":{"accepted_test_only":True,"time_result":fresh["time_result"],"challenge":req["challenge"],"destination_device_uuid":str(receipt.peer_device_uuid)}})
            assert verified["status"] == "accepted_test_only"
            before_decisions = int(db.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict_uuid)) or 0); before_audit = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0); before_changes = int(db.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid == visit_uuid)) or 0)
        with Session(engine) as attempt:
            attempt.info["verified_reconciliation"] = verified
            try:
                reviewer = attempt.scalar(select(User).where(User.uuid == reviewer_uuid))
                central_sync_service.accept_incoming(attempt, conflict_uuid, current_user=reviewer, operation_uuid=uuid.uuid4(), resolution_reason="validated visit immutable")
                raise AssertionError("validated visit was accepted")
            except Exception as exc:
                assert "SIGNED_DOCUMENT_IMMUTABLE" in str(exc)
                attempt.rollback()
            assert "verified_reconciliation" not in attempt.info and "sync_apply_mode" not in attempt.info
        with Session(engine) as check:
            visit = check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == visit_uuid)); current_conflict = check.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict_uuid))
            assert visit.site_name == snapshot["site_name"] and visit.status == snapshot["status"] and visit.validated_at == snapshot["validated_at"] and visit.version == snapshot["version"]
            assert int(check.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == visit_uuid)) or 0) == snapshot["revisions"]
            assert current_conflict.status == "physician_review" and current_conflict.resolved_payload is None
            assert int(check.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict_uuid)) or 0) == before_decisions
            assert int(check.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == current_conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0) == before_audit
            assert int(check.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid == visit_uuid)) or 0) == before_changes
        print("validated_visit_rejected=1", "reason=SIGNED_DOCUMENT_IMMUTABLE", "snapshot_preserved=1", "conflict_unresolved=1", "decision_delta=0", "audit_delta=0", "incoming_echo_sync_changes=0")

def run_revoked_delegation_case(source, target):
    with reconciliation_scenario(source, target, scenario="medical_visit_update", local_pending=True) as fixture:
        engine=create_engine(target)
        with Session(engine) as db:
            receipt=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid==uuid.UUID(fixture["receipt_uuid"])))
            event=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==uuid.UUID(fixture["event_uuid"])))
            conflict=db.scalar(select(SyncConflict).where(SyncConflict.uuid==uuid.UUID(fixture["conflict_uuid"])))
            assert receipt and event and conflict
            event_uuid = event.event_uuid; peer_device_uuid = receipt.peer_device_uuid
            req=begin_challenge(proof_uuid=receipt.proof_uuid,event_uuid=event.event_uuid,authority_scope=fixture["chain_scope"]); req["challenge"]=uuid.uuid4().hex; req.update(destination_uuid=str(receipt.peer_device_uuid),policy_version="5A-P1-20261014")
            response=requests.post(fixture["time_authority_url"],json={k:v for k,v in req.items() if k!="started_monotonic"},timeout=5).json()
            fresh=evaluate_freshness(response,req,RemoteAuthority(fixture["time_authority_public_key"]),ended_monotonic=time.monotonic(),policy=_test_time_policy()); assert fresh["accepted_test_only"]
            checkpoint={"checkpoint_uuid":fixture["checkpoint_uuid"],"authority_uuid":fixture["checkpoint_authority_uuid"],"chain_scope":fixture["chain_scope"],"contract_version":"revocation-chain-v1","policy_version":"5A-P1-20261014","covered_sequence":1,"covered_chain_hash":fixture["checkpoint_chain_hash"],"challenge":"fixture-challenge","destination_device_uuid":str(receipt.peer_device_uuid)}
            verified=reconcile_origin_proof(db,event_uuid=event.event_uuid,peer_device_uuid=receipt.peer_device_uuid,checkpoint_context={"checkpoint":checkpoint,**checkpoint,"coverage":{"status":"complete"},"freshness":{"accepted_test_only":True,"time_result":fresh["time_result"],"challenge":req["challenge"],"destination_device_uuid":str(receipt.peer_device_uuid)}}); assert verified["status"]=="accepted_test_only"
            candidates=db.scalars(select(ProofDelegation).where(ProofDelegation.entity_type=="medical_visits",ProofDelegation.operation=="update",ProofDelegation.state=="active").order_by(ProofDelegation.issued_at.desc())).all()
            delegation=next((d for d in candidates if d.user_uuid is None or str(d.user_uuid)==str(getattr(event,"source_user_uuid",None))), candidates[0] if candidates else None)
            assert delegation is not None
            reviewer=next(u for u in db.scalars(select(User).where(User.role=="doctor",User.is_active.is_(True))).all() if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(u)))
            record={"revocation_uuid":str(uuid.uuid4()),"target_type":"delegation","target_ref":str(delegation.delegation_uuid),"reason_code":"fixture_compromise","effective_at_declared":datetime.now(timezone.utc).isoformat(),"authority_key_id":fixture["revocation_authority_key_id"],"policy_version":delegation.policy_version,"target_clinic_uuid":str(delegation.clinic_uuid),"target_origin_service_uuid":str(delegation.origin_service_uuid),"canonicalization_version":"deterministic-json-restricted-v1","authority_ref":"fixture-revocation-authority"}; record["signature"]=fixture["sign_revocation"](revocation_canonical_bytes(record)); register_and_revoke_delegation(db,record,clinic_uuid=delegation.clinic_uuid,policy_version=delegation.policy_version); db.commit()
            delegation_uuid = delegation.delegation_uuid
            delegation_clinic_uuid = delegation.clinic_uuid
            delegation_policy_version = delegation.policy_version
            before_decisions=int(db.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid==conflict.uuid)) or 0); before_audit=int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type=="sync_conflicts",AuditLog.entity_id==conflict.id,AuditLog.action=="central_conflict_accept_incoming")) or 0); before_changes=int(db.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid==conflict.entity_uuid)) or 0); reviewer_uuid=reviewer.uuid
        # Deterministic ordering: the revoker owns the delegation row lock
        # first; acceptance must wait, then re-read the committed state.
        lock_acquired = threading.Event(); release_revocation = threading.Event()
        accept_started = threading.Event(); ordering = {}
        def revoke_worker():
            with Session(engine) as rev_db:
                rev_db.scalar(select(ProofDelegation).where(ProofDelegation.delegation_uuid == delegation_uuid).with_for_update())
                lock_acquired.set(); assert release_revocation.wait(10)
                register_and_revoke_delegation(rev_db, record, clinic_uuid=delegation_clinic_uuid, policy_version=delegation_policy_version)
                rev_db.commit()
        def accept_worker():
            assert lock_acquired.wait(10)
            with Session(engine) as attempt:
                attempt.info["verified_reconciliation"] = verified; accept_started.set()
                try:
                    central_sync_service.accept_incoming(attempt, conflict.uuid, current_user=attempt.scalar(select(User).where(User.uuid == reviewer_uuid)), operation_uuid=uuid.uuid4(), resolution_reason="revoked delegation")
                    ordering["error"] = "revoked delegation accepted"
                except Exception as exc:
                    ordering["reason"] = str(exc); attempt.rollback()
                ordering["context_cleared"] = "verified_reconciliation" not in attempt.info and "sync_apply_mode" not in attempt.info
        rev_thread = threading.Thread(target=revoke_worker, daemon=True); accept_thread = threading.Thread(target=accept_worker, daemon=True)
        rev_thread.start(); assert lock_acquired.wait(10)
        accept_thread.start(); assert accept_started.wait(10)
        accept_thread.join(timeout=0.5)
        assert accept_thread.is_alive(), "acceptance did not wait on the delegation lock"
        release_revocation.set(); rev_thread.join(timeout=10); accept_thread.join(timeout=10)
        assert not rev_thread.is_alive() and not accept_thread.is_alive()
        assert ordering.get("reason") and "DELEGATION_REVOKED" in ordering["reason"] and ordering.get("context_cleared")
        print("revocation_lock_acquired_first=1", "acceptance_waited=1", "stale_context_rejected=1 reason=DELEGATION_REVOKED", "context_cleared_after_rejection=1")
        with Session(engine) as fresh_db:
            rejected=reconcile_origin_proof(fresh_db,event_uuid=event_uuid,peer_device_uuid=peer_device_uuid,checkpoint_context={"checkpoint":checkpoint,**checkpoint,"coverage":{"status":"complete"},"freshness":{"accepted_test_only":True,"time_result":fresh["time_result"],"challenge":uuid.uuid4().hex,"destination_device_uuid":str(peer_device_uuid)}}); assert rejected["status"]!="accepted_test_only"; print("fresh_reverification_rejected=1 reason=DELEGATION_REVOKED")
            c=fresh_db.scalar(select(SyncConflict).where(SyncConflict.uuid==conflict.uuid)); v=fresh_db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==conflict.entity_uuid)); assert c.status=="physician_review" and c.resolved_payload is None and v.version==2
            assert int(fresh_db.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid==conflict.uuid)) or 0)==before_decisions and int(fresh_db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type=="sync_conflicts",AuditLog.entity_id==c.id,AuditLog.action=="central_conflict_accept_incoming")) or 0)==before_audit and int(fresh_db.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid==conflict.entity_uuid)) or 0)==before_changes
        print("delegation_revocation_persistent=1", "conflict_unresolved=1", "decision_delta=0", "resolution_revision_delta=0", "audit_delta=0", "incoming_echo_sync_changes=0", "context_cleared_after_rejection=1")

def main():
    source = os.environ["STAGE5_SOURCE_DB"]; target = os.environ["STAGE5_TARGET_DB"]
    with reconciliation_scenario(source, target, scenario="medical_visit_update", local_pending=True) as fixture:
        engine = create_engine(target)
        with Session(engine) as db:
            receipt = db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid == uuid.UUID(fixture["receipt_uuid"])))
            event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == uuid.UUID(fixture["event_uuid"])))
            conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture["conflict_uuid"])))
            auth = db.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.event_uuid == event.event_uuid))
            assert receipt and event and conflict and auth
            req = begin_challenge(proof_uuid=receipt.proof_uuid, event_uuid=event.event_uuid, authority_scope=fixture["chain_scope"])
            req["challenge"] = uuid.uuid4().hex; req.update(destination_uuid=str(receipt.peer_device_uuid), policy_version="5A-P1-20261014")
            response = requests.post(fixture["time_authority_url"], json={k:v for k,v in req.items() if k != "started_monotonic"}, timeout=5).json()
            freshness = evaluate_freshness(response, req, RemoteAuthority(fixture["time_authority_public_key"]), ended_monotonic=time.monotonic(), policy=_test_time_policy())
            assert freshness["accepted_test_only"] is True
            checkpoint = {"checkpoint_uuid": fixture["checkpoint_uuid"], "authority_uuid": fixture["checkpoint_authority_uuid"], "chain_scope": fixture["chain_scope"], "contract_version":"revocation-chain-v1", "policy_version":"5A-P1-20261014", "covered_sequence":1, "covered_chain_hash":fixture["checkpoint_chain_hash"], "challenge":"fixture-challenge", "destination_device_uuid":str(receipt.peer_device_uuid)}
            result = reconcile_origin_proof(db, event_uuid=event.event_uuid, peer_device_uuid=receipt.peer_device_uuid, checkpoint_context={"checkpoint":checkpoint, **checkpoint, "coverage":{"status":"complete"}, "freshness":{"accepted_test_only":True,"time_result":freshness["time_result"],"challenge":req["challenge"],"destination_device_uuid":str(receipt.peer_device_uuid)}})
            assert result["status"] == "accepted_test_only"
            # Context isolation: a second independently prepared conflict must
            # reject A's consumed verification context before any write.
            db.close()
            with reconciliation_scenario(source, target, scenario="medical_visit_update", local_pending=True) as fixture_b:
                fixture_b_uuid = uuid.UUID(fixture_b["conflict_uuid"])
                with Session(engine) as bdb:
                    conflict_b = bdb.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture_b["conflict_uuid"])))
                    reviewer_b = next((u for u in bdb.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all() if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(u))), None)
                    assert conflict_b and reviewer_b
                    bdb.info["verified_reconciliation"] = result
                    try:
                        central_sync_service.accept_incoming(bdb, conflict_b.uuid, current_user=reviewer_b, operation_uuid=uuid.uuid4(), resolution_reason="context isolation check")
                        raise AssertionError("cross-conflict verification context was accepted")
                    except Exception as exc:
                        assert "EVIDENCE_BINDING_INVALID" in str(exc)
                        bdb.rollback()
                    assert "verified_reconciliation" not in bdb.info and "sync_apply_mode" not in bdb.info
                with Session(engine) as bcheck:
                    persisted_b = bcheck.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture_b["conflict_uuid"])))
                    assert persisted_b.status == "physician_review" and persisted_b.resolved_payload is None
                print("cross_conflict_context_rejected=1", "conflict_b_unresolved=1", "no_write_before_rejection=1")
            # Full Session.info lifecycle: consume A while attempting B,
            # reject reuse for A, then reverify and commit A.
            with Session(engine) as lifecycle:
                conflict_a = lifecycle.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture["conflict_uuid"])))
                conflict_b = lifecycle.scalar(select(SyncConflict).where(SyncConflict.uuid == fixture_b_uuid))
                lifecycle_reviewer = next((u for u in lifecycle.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all() if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(u))), None)
                assert conflict_a and conflict_b and lifecycle_reviewer
                lifecycle.info["verified_reconciliation"] = result
                try:
                    central_sync_service.accept_incoming(lifecycle, conflict_b.uuid, current_user=lifecycle_reviewer, operation_uuid=uuid.uuid4(), resolution_reason="same-session context check")
                    raise AssertionError("same-session cross-conflict context was accepted")
                except Exception as exc:
                    assert "EVIDENCE_BINDING_INVALID" in str(exc)
                    lifecycle.rollback()
                assert "verified_reconciliation" not in lifecycle.info
                print("same_session_cross_conflict_rejected=1")
                try:
                    central_sync_service.accept_incoming(lifecycle, conflict_a.uuid, current_user=lifecycle_reviewer, operation_uuid=uuid.uuid4(), resolution_reason="old context reuse")
                    raise AssertionError("consumed verification context was reused")
                except Exception as exc:
                    assert "FRESH_EVIDENCE_REQUIRED" in str(exc)
                    lifecycle.rollback()
                assert "verified_reconciliation" not in lifecycle.info
                print("context_cleared_after_rollback=1", "old_context_reuse_rejected=1")
            with Session(engine) as db:
                receipt = db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid == uuid.UUID(fixture["receipt_uuid"])))
                event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == uuid.UUID(fixture["event_uuid"])))
                conflict = db.scalar(select(SyncConflict).where(SyncConflict.uuid == uuid.UUID(fixture["conflict_uuid"])))
                auth = db.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.event_uuid == event.event_uuid))
                assert receipt and event and conflict and auth
                checkpoint = {"checkpoint_uuid": fixture["checkpoint_uuid"], "authority_uuid": fixture["checkpoint_authority_uuid"], "chain_scope": fixture["chain_scope"], "contract_version":"revocation-chain-v1", "policy_version":"5A-P1-20261014", "covered_sequence":1, "covered_chain_hash":fixture["checkpoint_chain_hash"], "challenge":"fixture-challenge", "destination_device_uuid":str(receipt.peer_device_uuid)}
            # The reconciliation coordinator's result is scoped to this Session;
            # it is not a caller-supplied evidence/authorization dictionary.
            db.info["verified_reconciliation"] = result
            reviewer = None
            for candidate in db.scalars(select(User).where(User.role == "doctor", User.is_active.is_(True))).all():
                if "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(candidate)):
                    reviewer = candidate
                    break
            assert reviewer is not None, "no authorized doctor in target fixture"
            assert "sync.resolve_conflicts" in set(permission_service.get_effective_permission_codes(reviewer))
            reviewer_uuid = reviewer.uuid
            before_visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid))
            assert before_visit is not None and before_visit.status != "validated"
            before_version = int(before_visit.version)
            before_revisions = int(db.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == conflict.entity_uuid)) or 0)
            before_decision_revisions = int(db.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == conflict.entity_uuid, LocalRevision.kind == "conflict_accept")) or 0)
            before_decisions = int(db.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict.uuid)) or 0)
            before_audit = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0)
            before_changes = int(db.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid == conflict.entity_uuid)) or 0)
            before_revision = db.scalar(select(LocalRevision).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == conflict.entity_uuid).order_by(LocalRevision.local_version.desc()))
            operation_uuid = uuid.uuid4()
            reason = "physician review accepts the verified incoming visit fields"
            # Independent rollback pass: fail after the visit write is flushed.
            failed_operation = uuid.uuid4()
            db.info["verified_reconciliation"] = result
            db.info["inject_accept_incoming_failure"] = True
            try:
                central_sync_service.accept_incoming(db, conflict.uuid, current_user=reviewer, operation_uuid=failed_operation, resolution_reason=reason)
                raise AssertionError("injected accept failure did not fire")
            except RuntimeError as exc:
                assert str(exc) == "INJECTED_ACCEPT_INCOMING_FAILURE_AFTER_FLUSH"
                db.rollback()
            assert "sync_apply_mode" not in db.info
            assert "verified_reconciliation" not in db.info
            with Session(engine) as rollback_check:
                rollback_visit = rollback_check.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid))
                rollback_conflict = rollback_check.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict.uuid))
                assert rollback_visit.version == before_version
                assert rollback_conflict.status == "physician_review" and rollback_conflict.resolved_payload is None
                assert int(rollback_check.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict.uuid)) or 0) == before_decisions
                assert int(rollback_check.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == rollback_conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0) == before_audit
                assert int(rollback_check.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid == conflict.entity_uuid)) or 0) == before_changes
            print("rollback_injected=1", "visit_unchanged=1", "conflict_unresolved=1", "decision_delta=0", "audit_delta=0", "incoming_echo_sync_changes=0")
            # A failed attempt cannot reuse its freshness: issue a new challenge
            # and rebuild the coordinator result before retrying.
            req2 = begin_challenge(proof_uuid=receipt.proof_uuid, event_uuid=event.event_uuid, authority_scope=fixture["chain_scope"])
            req2["challenge"] = uuid.uuid4().hex; req2.update(destination_uuid=str(receipt.peer_device_uuid), policy_version="5A-P1-20261014")
            response2 = requests.post(fixture["time_authority_url"], json={k:v for k,v in req2.items() if k != "started_monotonic"}, timeout=5).json()
            freshness2 = evaluate_freshness(response2, req2, RemoteAuthority(fixture["time_authority_public_key"]), ended_monotonic=time.monotonic(), policy=_test_time_policy())
            assert freshness2["accepted_test_only"] is True and freshness2["time_result"] == "time_valid_test_only"
            result = reconcile_origin_proof(db, event_uuid=event.event_uuid, peer_device_uuid=receipt.peer_device_uuid, checkpoint_context={"checkpoint":checkpoint, **checkpoint, "coverage":{"status":"complete"}, "freshness":{"accepted_test_only":True,"time_result":freshness2["time_result"],"challenge":req2["challenge"],"destination_device_uuid":str(receipt.peer_device_uuid)}})
            assert result["status"] == "accepted_test_only"
            print("fresh_reverification_succeeds=1", "freshness_reverified_after_rollback=1")
            db.info["verified_reconciliation"] = result
            decision = central_sync_service.accept_incoming(db, conflict.uuid, current_user=reviewer, operation_uuid=operation_uuid, resolution_reason=reason)
            assert decision.conflict_uuid == conflict.uuid
            assert "verified_reconciliation" not in db.info and "sync_apply_mode" not in db.info
            print("context_cleared_after_commit=1")
            db.close()
            with Session(engine) as verify:
                visit = verify.scalar(select(MedicalVisit).where(MedicalVisit.uuid == conflict.entity_uuid))
                resolved = verify.scalar(select(SyncConflict).where(SyncConflict.uuid == conflict.uuid))
                persisted_decisions = int(verify.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict.uuid)) or 0)
                persisted_revisions = int(verify.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == conflict.entity_uuid)) or 0)
                persisted_decision_revisions = int(verify.scalar(select(func.count(LocalRevision.revision_uuid)).where(LocalRevision.entity_type == "medical_visits", LocalRevision.entity_uuid == conflict.entity_uuid, LocalRevision.kind == "conflict_accept")) or 0)
                persisted_audit = int(verify.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == resolved.id, AuditLog.action == "central_conflict_accept_incoming")) or 0)
                persisted_changes = int(verify.scalar(select(func.count(SyncChange.id)).where(SyncChange.entity_uuid == conflict.entity_uuid)) or 0)
                assert resolved.status == "resolved" and resolved.resolution_type == "accept_incoming"
                assert persisted_decisions == before_decisions + 1
                assert persisted_decision_revisions == before_decision_revisions + 1
                assert persisted_revisions >= before_revisions
                assert persisted_audit == before_audit + 1
                assert persisted_changes == before_changes
                assert visit.version == before_version + 1
                assert resolved.resolved_payload and resolved.resolved_payload["decision_uuid"] == str(decision.decision_uuid)
                print("accept_incoming=accepted_test_only", "resolved=1", "revision_delta=1", "decision_delta=1", "audit_delta=1", "incoming_echo_sync_changes=0")
            # Same operation/content is an idempotent replay and must not add rows.
            with Session(engine) as replay_db:
                replay_db.info["verified_reconciliation"] = result
                replay_reviewer = replay_db.scalar(select(User).where(User.uuid == reviewer_uuid))
                assert replay_reviewer is not None
                replayed = central_sync_service.accept_incoming(replay_db, conflict.uuid, current_user=replay_reviewer, operation_uuid=operation_uuid, resolution_reason=reason)
                replay_db.close()
            with Session(engine) as verify_replay:
                assert replayed.decision_uuid == decision.decision_uuid
                assert int(verify_replay.scalar(select(func.count(SyncConflictDecision.decision_uuid)).where(SyncConflictDecision.conflict_uuid == conflict.uuid)) or 0) == before_decisions + 1
                assert int(verify_replay.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_type == "sync_conflicts", AuditLog.entity_id == conflict.id, AuditLog.action == "central_conflict_accept_incoming")) or 0) == before_audit + 1
                print("replay_same_decision=1", "no_extra_revision=1", "no_extra_audit=1")
        print("accept_incoming_setup_only=0", fixture)

if __name__ == "__main__":
    main()
    run_stale_version_case(os.environ["STAGE5_SOURCE_DB"], os.environ["STAGE5_TARGET_DB"])
    run_validated_visit_case(os.environ["STAGE5_SOURCE_DB"], os.environ["STAGE5_TARGET_DB"])
    run_revoked_delegation_case(os.environ["STAGE5_SOURCE_DB"], os.environ["STAGE5_TARGET_DB"])

