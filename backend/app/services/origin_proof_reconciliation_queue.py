import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, or_
from app.models.origin_proof_reconciliation_task import OriginProofReconciliationTask
from app.models.revocation_checkpoint import RevocationCheckpoint
from app.services.revocation_checkpoint_service import verify_checkpoint_signature
from app.services.revocation_chain_service import check_coverage

def enqueue(db, *, event_uuid, proof_uuid, peer_device_uuid, chain_scope):
    q=select(OriginProofReconciliationTask).where(OriginProofReconciliationTask.event_uuid==event_uuid,OriginProofReconciliationTask.proof_uuid==proof_uuid,OriginProofReconciliationTask.peer_device_uuid==peer_device_uuid,OriginProofReconciliationTask.chain_scope==chain_scope)
    row=db.scalar(q)
    if row: return row
    now=datetime.now(timezone.utc); row=OriginProofReconciliationTask(task_uuid=uuid.uuid4(),event_uuid=event_uuid,proof_uuid=proof_uuid,peer_device_uuid=peer_device_uuid,chain_scope=chain_scope,state="pending",attempts=0,available_at=now,created_at=now,updated_at=now); db.add(row); db.flush(); return row

def claim(db, *, worker_id, lease_seconds=60, task_uuid=None):
    now=datetime.now(timezone.utc); row=db.scalar(select(OriginProofReconciliationTask).where(*(([OriginProofReconciliationTask.task_uuid == task_uuid] if task_uuid else []) + [OriginProofReconciliationTask.state.in_(("pending","leased")),OriginProofReconciliationTask.available_at<=now,or_(OriginProofReconciliationTask.lease_until.is_(None),OriginProofReconciliationTask.lease_until<now)])).with_for_update(skip_locked=True).order_by(OriginProofReconciliationTask.created_at))
    if not row:return None
    row.state="leased"; row.claimed_by=worker_id; row.lease_until=now+timedelta(seconds=lease_seconds); row.attempts+=1; row.updated_at=now; db.flush(); return row

def complete(db,row,*,worker_id,result=None):
    if row.state != "leased" or row.claimed_by != worker_id or (row.lease_until and row.lease_until < datetime.now(timezone.utc)):
        raise PermissionError("RECONCILIATION_LEASE_NOT_OWNED")
    row.state="completed"; row.lease_until=None; row.updated_at=datetime.now(timezone.utc)
    if result is not None:
        import hashlib, json
        row.result_payload=result
        row.result_fingerprint=result.get("input_fingerprint") or (result.get("verification") or {}).get("input_fingerprint") or hashlib.sha256(json.dumps(result,sort_keys=True,default=str,separators=(",",":")).encode()).hexdigest()
    db.flush()
def fail(db,row,error): row.state="pending"; row.last_error=str(error)[:240]; row.available_at=datetime.now(timezone.utc)+timedelta(seconds=min(300,max(1,row.attempts))); row.lease_until=None; row.updated_at=datetime.now(timezone.utc); db.flush()

def choose_checkpoint(db, *, binding, authority_public_key):
    if getattr(binding, "state", None) != "active": return {"status": "blocked", "reason": "TRUST_BINDING_REVOKED"}
    rows=db.scalars(select(RevocationCheckpoint).where(RevocationCheckpoint.authority_uuid==binding.revocation_authority_uuid,RevocationCheckpoint.chain_scope==binding.chain_scope,RevocationCheckpoint.contract_version==binding.chain_contract_version,RevocationCheckpoint.policy_version==binding.policy_version).order_by(RevocationCheckpoint.covered_sequence.desc())).all()
    valid=[]
    for cp in rows:
        if verify_checkpoint_signature({"checkpoint_uuid":str(cp.checkpoint_uuid),"authority_uuid":str(cp.authority_uuid),"authority_key_id":cp.authority_key_id,"chain_scope":cp.chain_scope,"contract_version":cp.contract_version,"policy_version":cp.policy_version,"covered_sequence":cp.covered_sequence,"covered_chain_hash":cp.covered_chain_hash,"challenge":cp.challenge,"destination_device_uuid":str(cp.destination_device_uuid),"signature":cp.signature},authority_public_key)!="valid": continue
        coverage=check_coverage(db,authority_uuid=cp.authority_uuid,chain_scope=cp.chain_scope,checkpoint_sequence=cp.covered_sequence,checkpoint_hash=cp.covered_chain_hash)
        if coverage["status"]=="complete": valid.append(cp)
    if not rows: return {"status":"blocked","reason":"CHECKPOINT_NO_MATCHING_RECORD"}
    if not valid: return {"status":"blocked","reason":"CHECKPOINT_SIGNATURE_OR_COVERAGE_INVALID"}
    if len([x for x in valid if x.covered_sequence==valid[0].covered_sequence])>1:return {"status":"blocked","reason":"CHECKPOINT_AMBIGUOUS"}
    return {"status":"resolved","checkpoint":valid[0]}


def consume_one(db, *, worker_id, authority_public_key, freshness_context=None, task_uuid=None):
    task=claim(db,worker_id=worker_id,task_uuid=task_uuid)
    if task is None: return None
    try:
        from app.models.proof_trust_binding import ProofTrustBinding
        from app.models.origin_proof_transport import OriginProofTransportReceipt
        from app.services.proof_trust_binding_service import resolve_local_binding
        receipt=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==task.event_uuid,OriginProofTransportReceipt.proof_uuid==task.proof_uuid,OriginProofTransportReceipt.peer_device_uuid==task.peer_device_uuid))
        if receipt is None: raise ValueError("PROOF_RECEIPT_NOT_FOUND")
        local=resolve_local_binding(db,proof=receipt.proof,clinic_uuid=receipt.proof.get("clinic_uuid"),origin_service_uuid=receipt.proof.get("origin_service_uuid"),policy_version=receipt.proof.get("authorization_policy_version"))
        if local.get("status") != "resolved": raise ValueError(local.get("reason","TRUST_BINDING_BLOCKED"))
        selected=choose_checkpoint(db,binding=local["binding"],authority_public_key=authority_public_key)
        if selected.get("status") != "resolved": raise ValueError(selected["reason"])
        if freshness_context is None: raise ValueError("FRESHNESS_EVIDENCE_REQUIRED")
        from app.services.origin_proof_reconciliation import reconcile_origin_proof
        result=reconcile_origin_proof(db,event_uuid=task.event_uuid,peer_device_uuid=task.peer_device_uuid,checkpoint_context={"freshness":freshness_context,**freshness_context,"checkpoint":{"checkpoint_uuid":str(selected["checkpoint"].checkpoint_uuid),"authority_uuid":str(selected["checkpoint"].authority_uuid),"contract_version":selected["checkpoint"].contract_version,"policy_version":selected["checkpoint"].policy_version,"challenge":selected["checkpoint"].challenge,"destination_device_uuid":str(selected["checkpoint"].destination_device_uuid),"chain_scope":selected["checkpoint"].chain_scope,"covered_sequence":selected["checkpoint"].covered_sequence,"covered_chain_hash":selected["checkpoint"].covered_chain_hash},"coverage":{"status":"complete"},"challenge":selected["checkpoint"].challenge,"destination_device_uuid":str(selected["checkpoint"].destination_device_uuid),"chain_scope":selected["checkpoint"].chain_scope,"covered_sequence":selected["checkpoint"].covered_sequence,"covered_chain_hash":selected["checkpoint"].covered_chain_hash,"contract_version":selected["checkpoint"].contract_version,"policy_version":selected["checkpoint"].policy_version,"checkpoint_uuid":str(selected["checkpoint"].checkpoint_uuid),"authority_uuid":str(selected["checkpoint"].authority_uuid)})
        if result.get("status") != "accepted_test_only":
            fail(db,task,result.get("reason","RECONCILIATION_BLOCKED")); return result
        complete(db,task,worker_id=worker_id,result=result); return result
    except Exception as exc:
        fail(db,task,exc); return {"status":"blocked","reason":str(exc)}




