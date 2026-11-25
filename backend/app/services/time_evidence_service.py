"""Validation/storage contract helpers for signed time evidence (no eligibility)."""
import hashlib, json, base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.time_evidence import TimeEvidence
TIME_EVIDENCE_CANONICALIZATION='time-evidence-deterministic-json-v1'
TIME_EVIDENCE_DOMAIN='medical-folder/time-evidence/v1'
TIME_EVIDENCE_FIELDS=('evidence_uuid','proof_uuid','event_uuid','content_sha256','authority_key_id','sequence','chain_scope','issued_at_declared','uncertainty_seconds','policy_version')

def canonical_evidence_bytes(evidence):
    payload={'domain':TIME_EVIDENCE_DOMAIN,'canonicalization':TIME_EVIDENCE_CANONICALIZATION}
    for key in TIME_EVIDENCE_FIELDS:
        value=evidence.get(key)
        if value is not None:
            payload[key]=str(value) if key.endswith('_uuid') or key.endswith('_at') else value
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def verify_evidence_signature(evidence, public_key_b64):
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(evidence['signature']),canonical_evidence_bytes(evidence)); return 'valid'
    except (ValueError,KeyError,InvalidSignature): return 'invalid'

def evidence_fingerprint(evidence: dict) -> str:
    return hashlib.sha256(canonical_evidence_bytes(evidence)).hexdigest()

def validate_time_evidence(evidence: dict, *, proof_uuid, event_uuid, content_sha256, authority):
    required=("evidence_uuid","proof_uuid","event_uuid","content_sha256","authority_key_id","sequence","chain_scope","signature")
    if any(evidence.get(k) in (None, "") for k in required): return "invalid"
    if str(evidence["proof_uuid"]) != str(proof_uuid) or str(evidence["event_uuid"]) != str(event_uuid): return "binding_mismatch"
    if evidence["content_sha256"] != content_sha256: return "binding_mismatch"
    if evidence["chain_scope"] != authority.get("chain_scope"): return "authority_scope_mismatch"
    if type(evidence["sequence"]) is not int or evidence["sequence"] < 1: return "sequence_invalid"
    if verify_evidence_signature(evidence, authority.get("public_key", "")) != "valid": return "signature_invalid"
    return "valid"

def sequence_transition(previous, incoming):
    if previous is None: return "accepted_initial" if incoming == 1 else "gap"
    if incoming == previous: return "idempotent"  # caller must compare fingerprint
    if incoming == previous + 1: return "accepted_next"
    if incoming > previous + 1: return "gap"
    return "out_of_order"

def store_time_evidence(db, evidence: dict, *, proof_uuid, event_uuid, content_sha256, authority):
    result=validate_time_evidence(evidence, proof_uuid=proof_uuid,event_uuid=event_uuid,content_sha256=content_sha256,authority=authority)
    digest=evidence_fingerprint(evidence)
    existing=db.scalar(select(TimeEvidence).where(TimeEvidence.proof_uuid==proof_uuid,TimeEvidence.evidence_uuid==evidence.get('evidence_uuid')))
    if existing is not None:
        if existing.evidence_sha256 != digest: raise ValueError('TIME_EVIDENCE_CONTENT_MISMATCH')
        return existing
    row=TimeEvidence(evidence_uuid=evidence['evidence_uuid'],proof_uuid=proof_uuid,event_uuid=event_uuid,content_sha256=content_sha256,chain_scope=evidence['chain_scope'],sequence=evidence['sequence'],evidence_sha256=digest,evidence=evidence,validation_result=result,validation_reason=result,created_at=datetime.now(timezone.utc))
    db.add(row); db.flush()
    if db.info.get('time_evidence_fail_after_insert'): raise RuntimeError('TIME_EVIDENCE_SAVE_FAILED')
    return row
