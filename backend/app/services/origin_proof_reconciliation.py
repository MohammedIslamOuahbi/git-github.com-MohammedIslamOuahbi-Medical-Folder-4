"""Proof-before-event reconciliation; never writes business tables."""
from sqlalchemy import select
import uuid
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.sync_transport import SyncTransportEvent
from app.services.proof_verification_service import (validate_required_fields, verify_binding,
    verify_signature, verify_key_scope, verify_delegation_scope, evaluate_time_window)
from app.models.proof_trust import ProofTrustedKey, ProofDelegation
from app.services.sync_application_evaluation_service import evaluate_event


def reconcile_origin_proof(db, *, event_uuid, peer_device_uuid, checkpoint_context=None):
    receipt = db.scalar(select(OriginProofTransportReceipt).where(
        OriginProofTransportReceipt.event_uuid == event_uuid,
        OriginProofTransportReceipt.peer_device_uuid == peer_device_uuid,
    ))
    event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == event_uuid))
    if receipt is None:
        return {"status": "pending_proof", "reason": "PROOF_NOT_RECEIVED"}
    if event is None:
        return {"status": "pending_event", "reason": "EVENT_NOT_RECEIVED"}
    proof = receipt.proof
    # Authorization evidence is local, durable evidence; it is never inferred
    # from the evidence envelope itself. Expected operation/content/actor
    # values come from the trusted OriginProof and transport event.
    from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
    auth_rows=db.scalars(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.event_uuid==event_uuid, AuthorizationEvidenceRecord.operation_uuid==proof.get("operation_uuid"))).all()
    if len(auth_rows) == 0:
        return {"status":"rejected","reason":"AUTHORIZATION_EVIDENCE_MISSING","business_application":0}
    if len(auth_rows) != 1:
        return {"status":"rejected","reason":"AUTHORIZATION_EVIDENCE_AMBIGUOUS","business_application":0}
    auth_record=auth_rows[0]
    from app.models.proof_trust import ProofTrustedKey
    from app.services.authorization_evidence_service import verify_authorization_evidence, evidence_fingerprint
    auth_key=db.scalar(select(ProofTrustedKey).where(ProofTrustedKey.key_id==auth_record.issuer_key_id, ProofTrustedKey.origin_service_uuid==uuid.UUID(str(auth_record.envelope.get("issuer_uuid")))))
    if auth_key is None:
        return {"status":"rejected","reason":"AUTHORIZATION_ISSUER_KEY_UNTRUSTED","business_application":0}
    auth_status, auth_reason=verify_authorization_evidence(auth_record.envelope, public_key_b64=auth_key.public_key, expected={"subject_user_uuid":str(proof.get("origin_user_uuid")),"operation_uuid":str(proof.get("operation_uuid")),"event_uuid":str(event.event_uuid),"entity_type":event.entity_type,"entity_uuid":str(event.entity_uuid),"content_sha256":event.content_sha256,"clinic_uuid":str(event.source_clinic_uuid),"scope":auth_record.scope,"policy_version":proof.get("authorization_policy_version")}, trusted_issuer_uuid=uuid.UUID(str(auth_key.origin_service_uuid)), trusted_issuer_scope=auth_record.scope)
    if auth_status != "accepted_test_only":
        return {"status":"rejected","reason":auth_reason,"business_application":0}
    if validate_required_fields(proof) != "valid":
        return {"status": "rejected", "reason": "PROOF_FIELDS_INVALID"}
    binding = verify_binding(proof, event_uuid=event.event_uuid,
                             content_sha256=event.content_sha256,
                             clinic_uuid=event.source_clinic_uuid,
                             entity_type=event.entity_type,
                             entity_uuid=event.entity_uuid,
                             revision_uuid=event.revision_uuid,
                             operation=event.operation)
    if binding != "valid":
        return {"status": "rejected", "reason": "PROOF_EVENT_BINDING_MISMATCH"}
    key=db.get(ProofTrustedKey, proof.get("signing_key_id"))
    signature=verify_signature(proof, key.public_key if key else "")
    trusted_origin_service = uuid.UUID(str(proof.get("origin_service_uuid"))) if proof.get("origin_service_uuid") else None
    key_scope=verify_key_scope(proof,key,clinic_uuid=event.source_clinic_uuid,
        origin_service_uuid=trusted_origin_service, origin_device_uuid=uuid.UUID(str(proof.get("origin_device_uuid"))))
    delegation=db.scalar(select(ProofDelegation).where(ProofDelegation.delegation_uuid==proof.get("authorization_reference")))
    delegation_scope=verify_delegation_scope(proof,delegation,clinic_uuid=event.source_clinic_uuid,
        origin_service_uuid=trusted_origin_service,user_uuid=uuid.UUID(str(proof.get("origin_user_uuid"))),
        entity_type=event.entity_type,operation=event.operation,policy_version=proof.get("authorization_policy_version"))
    time_result=evaluate_time_window(issued_at=proof.get("issued_at"), evaluation_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), trusted_evidence=None)
    from app.services.proof_verification_service import evaluate_revocation_order
    revocation_result=evaluate_revocation_order(issued_at=proof.get("issued_at"), revoked_at=None, order_evidence=None)
    details={"signature":signature,"binding":binding,"key_scope":key_scope,"delegation_scope":delegation_scope,"time":time_result,"revocation":"not_resolved",
             "scope_fields":{"clinic":{"proof":str(proof.get("clinic_uuid")),"record":str(getattr(key,"clinic_uuid",None))},
             "key":{"proof":str(proof.get("signing_key_id")),"record":str(getattr(key,"key_id",None)),"state":str(getattr(key,"state",None)),"algorithm":str(getattr(key,"algorithm",None)),"canonicalization":str(getattr(key,"canonicalization_version",None))},
             "origin_service":{"proof":str(proof.get("origin_service_uuid")),"record":str(getattr(key,"origin_service_uuid",None))},
             "origin_device":{"proof":str(proof.get("origin_device_uuid")),"record":str(getattr(key,"origin_device_uuid",None))},
             "user":{"proof":str(proof.get("origin_user_uuid")),"record":str(getattr(delegation,"user_uuid",None))},
             "entity_type":{"proof":str(proof.get("entity_type")),"record":str(getattr(delegation,"entity_type",None))},
             "operation":{"proof":str(proof.get("operation")),"record":str(getattr(delegation,"operation",None))},
             "policy_version":{"proof":str(proof.get("authorization_policy_version")),"record":str(getattr(delegation,"policy_version",None))}}}
    details["revocation"] = revocation_result
    # Optional isolated-test evidence bundle. Production callers omit it and
    # remain blocked; no caller-supplied boolean is trusted.
    if checkpoint_context is not None:
        checkpoint = checkpoint_context.get("checkpoint") or {}
        coverage = checkpoint_context.get("coverage") or {}
        freshness = checkpoint_context.get("freshness") or {}
        comparisons=[]
        def cmp(name, expected, actual):
            comparisons.append({"condition":name,"expected":str(expected),"actual":str(actual),"expected_type":type(expected).__name__,"actual_type":type(actual).__name__,"match":str(expected)==str(actual)})
        cmp("checkpoint_uuid", checkpoint_context.get("checkpoint_uuid"), checkpoint.get("checkpoint_uuid"))
        cmp("authority_uuid", checkpoint_context.get("authority_uuid"), checkpoint.get("authority_uuid"))
        cmp("chain_scope", checkpoint_context.get("chain_scope"), checkpoint.get("chain_scope"))
        cmp("contract_version", checkpoint_context.get("contract_version"), checkpoint.get("contract_version"))
        cmp("policy_version", checkpoint_context.get("policy_version"), checkpoint.get("policy_version"))
        cmp("covered_sequence", checkpoint_context.get("covered_sequence"), checkpoint.get("covered_sequence"))
        cmp("covered_chain_hash", checkpoint_context.get("covered_chain_hash"), checkpoint.get("covered_chain_hash"))
        cmp("destination_device_uuid", checkpoint_context.get("destination_device_uuid"), checkpoint.get("destination_device_uuid"))
        checkpoint_ok=all(x["match"] for x in comparisons)
        details["checkpoint"] = {"binding": "valid" if checkpoint_ok else "mismatch",
            "covered_sequence": checkpoint.get("covered_sequence"),
            "covered_chain_hash": checkpoint.get("covered_chain_hash"),
            "coverage": coverage.get("status"), "freshness": freshness.get("time_result"),
            "evidence_fingerprint": checkpoint_context.get("evidence_fingerprint")}
        if not checkpoint_ok or coverage.get("status") != "complete" or not freshness.get("accepted_test_only"):
            return {"status": "rejected", "reason": "CHECKPOINT_COVERAGE_OR_FRESHNESS_INVALID", "verification": details, "checkpoint_debug": {"checkpoint_ok": checkpoint_ok, "checkpoint": checkpoint, "context": {k: checkpoint_context.get(k) for k in ("challenge","destination_device_uuid","chain_scope","covered_sequence","covered_chain_hash")}, "freshness": freshness}, "business_application": 0}
    if signature != "valid" or key_scope != "valid" or delegation_scope != "valid":
        return {"status":"rejected","reason":"PROOF_TRUST_OR_DELEGATION_INVALID","verification":details}
    authorization_payload = dict(auth_record.envelope)
    authorization_payload.update({"source":"authorization_evidence","reference":str(auth_record.evidence_uuid),"grant_id":auth_record.envelope_sha256,"verification_status":auth_status})
    decision=evaluate_event(db,event_uuid,policy_version=proof.get("authorization_policy_version"),authorization_evidence=authorization_payload)
    if checkpoint_context is not None:
        details["authorization"]={"status":auth_status,"evidence_uuid":str(auth_record.evidence_uuid),"envelope_sha256":auth_record.envelope_sha256,"trust_reference":auth_record.trust_reference,"issuer_key_id":auth_record.issuer_key_id,"event_uuid":str(event.event_uuid)}
        details["input_fingerprint"] = decision.input_fingerprint
        return {"status":"accepted_test_only","reason":"VERIFIED_WITH_CHECKPOINT_AND_FRESHNESS","verification":details,"input_fingerprint":decision.input_fingerprint,"application_decision":decision.decision,"business_application":0}
    return {"status":"rejected","reason":"TIME_INDETERMINATE","verification":details,"application_decision":decision.decision}


def schedule_origin_proof_reconciliation(event_uuid, peer_device_uuid):
    """Test-only post-commit hook. It opens a new session and never carries the
    receive transaction across evaluation/network work. Missing local evidence
    remains blocked and can be retried by the caller.
    """
    import os, logging
    if os.environ.get("ORIGIN_PROOF_RECONCILIATION_TEST") != "1":
        return {"status": "disabled", "reason": "TEST_RECONCILIATION_DISABLED"}
    from app.database import SessionLocal
    with SessionLocal() as session:
        from app.models.origin_proof_transport import OriginProofTransportReceipt
        receipt = session.scalar(__import__('sqlalchemy').select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid == event_uuid, OriginProofTransportReceipt.peer_device_uuid == peer_device_uuid))
        if receipt is not None:
            from app.services.proof_trust_binding_service import resolve_local_binding
            from app.services.origin_proof_reconciliation_queue import enqueue
            local = resolve_local_binding(session, proof=receipt.proof, clinic_uuid=receipt.proof.get('clinic_uuid'), origin_service_uuid=receipt.proof.get('origin_service_uuid'), policy_version=receipt.proof.get('authorization_policy_version'))
            if local.get('status') == 'resolved':
                enqueue(session, event_uuid=event_uuid, proof_uuid=receipt.proof_uuid, peer_device_uuid=peer_device_uuid, chain_scope=local['chain_scope'])
                session.commit()
        result = reconcile_origin_proof(session, event_uuid=event_uuid, peer_device_uuid=peer_device_uuid)
        session.rollback()
    logging.getLogger("sync.origin_proof").info("reconciliation_result status=%s reason=%s event=%s", result.get("status"), result.get("reason"), event_uuid)
    return result
