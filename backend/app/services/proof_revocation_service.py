from __future__ import annotations
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.proof_trust import ProofTrustedKey,ProofRevocation,ProofDelegation
from app.services.proof_verification_service import verify_revocation_signature,verify_revocation_authority
SUPPORTED_TARGETS={"key","delegation","proof"}
ALLOWED_FIELDS={"revocation_uuid","target_type","target_ref","reason_code","effective_at_declared","authority_key_id","policy_version","target_clinic_uuid","target_origin_service_uuid","canonicalization_version","authority_ref","signature","recorded_at"}
def parse_revocation_json(raw: str) -> dict:
 def pairs(items):
  out={}
  for k,v in items:
   if k in out: raise ValueError("REVOCATION_DUPLICATE_FIELD")
   out[k]=v
  return out
 value=json.loads(raw, object_pairs_hook=pairs)
 if not isinstance(value,dict): raise ValueError("REVOCATION_JSON_INVALID")
 return value
def register_revocation(db, record:dict, *, clinic_uuid, target_type, policy_version):
 if set(record)-ALLOWED_FIELDS: raise ValueError("REVOCATION_UNSUPPORTED_FIELD")
 if record.get("target_type") not in SUPPORTED_TARGETS or record.get("target_type") != target_type: raise ValueError("REVOCATION_TARGET_UNSUPPORTED")
 if record.get("policy_version") != policy_version or not record.get("target_ref") or not record.get("authority_key_id") or not record.get("reason_code") or not record.get("effective_at_declared") or not record.get("authority_ref") or not record.get("signature") or record.get("canonicalization_version") != "deterministic-json-restricted-v1" or not record.get("target_clinic_uuid") or not record.get("target_origin_service_uuid"): raise ValueError("REVOCATION_FIELDS_INVALID")
 try: rid=uuid.UUID(str(record["revocation_uuid"]))
 except (ValueError,TypeError,KeyError): raise ValueError("REVOCATION_UUID_INVALID")
 key=db.get(ProofTrustedKey,record["authority_key_id"])
 if key is None: raise ValueError("REVOCATION_AUTHORITY_UNKNOWN")
 if verify_revocation_signature(record,key.public_key if key else "") != "valid": raise ValueError("REVOCATION_SIGNATURE_INVALID")
 if verify_revocation_authority(record,key,clinic_uuid=clinic_uuid,target_type=target_type,policy_version=policy_version) != "valid": raise ValueError("REVOCATION_AUTHORITY_SCOPE_INVALID")
 existing=db.get(ProofRevocation,rid)
 if existing is not None:
  if existing.signature==record.get("signature") and existing.target_ref==record.get("target_ref") and existing.reason_code==record.get("reason_code"): return existing
  raise ValueError("REVOCATION_UUID_REUSE")
 if target_type=="key" and db.get(ProofTrustedKey,record["target_ref"]) is None: raise ValueError("REVOCATION_TARGET_NOT_FOUND")
 if target_type=="delegation":
  delegation=db.get(ProofDelegation,record["target_ref"])
  if delegation is None: raise ValueError("REVOCATION_TARGET_NOT_FOUND")
  if str(delegation.clinic_uuid)!=str(clinic_uuid) or str(delegation.origin_service_uuid)!=str(key.origin_service_uuid): raise ValueError("REVOCATION_AUTHORITY_SCOPE_INVALID")
 if target_type=="proof": raise ValueError("REVOCATION_TARGET_UNVERIFIABLE")
 row=ProofRevocation(revocation_uuid=rid,target_type=target_type,target_ref=record["target_ref"],reason_code=record["reason_code"],effective_at_declared=record["effective_at_declared"],authority_ref=record["authority_ref"],recorded_at=record.get("recorded_at") or datetime.now(timezone.utc),authority_key_id=record["authority_key_id"],policy_version=record["policy_version"],signature=record["signature"],canonicalization_version=record["canonicalization_version"],target_clinic_uuid=record["target_clinic_uuid"],target_origin_service_uuid=record["target_origin_service_uuid"]); db.add(row); db.flush()
 if db.info.get("stage5a_fail_revocation_before_commit"): raise RuntimeError("INJECTED_REVOCATION_FAILURE")
 return row

def register_and_revoke_delegation(db, record: dict, *, clinic_uuid, policy_version):
    """Validate a signed delegation revocation, then transition the delegation atomically."""
    # Serialize revocation with any acceptance that re-checks this delegation.
    # The caller owns commit/rollback; this lock is held until that boundary.
    delegation = db.scalar(select(ProofDelegation).where(
        ProofDelegation.delegation_uuid == uuid.UUID(str(record["target_ref"]))
    ).execution_options(populate_existing=True).with_for_update())
    if delegation is None:
        raise ValueError("REVOCATION_TARGET_NOT_FOUND")
    row = register_revocation(db, record, clinic_uuid=clinic_uuid, target_type="delegation", policy_version=policy_version)
    delegation.state = "revoked"
    db.add(delegation)
    db.flush()
    return row
