from __future__ import annotations
import base64,json,uuid,re,hashlib
from datetime import datetime,timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
CANONICALIZATION_VERSION="deterministic-json-restricted-v1"
DELEGATION_DAYS=7
def verification_input_fingerprint(*,proof,event_uuid,content_sha256,key_version,delegation_version,revocation_version,policy_version,time_evidence_version):
 payload={"proof":proof,"event_uuid":str(event_uuid),"content_sha256":content_sha256,"key_version":key_version,"delegation_version":delegation_version,"revocation_version":revocation_version,"policy_version":policy_version,"time_evidence_version":time_evidence_version}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def verification_input_fingerprint_from_records(*,db,proof,event_uuid,content_sha256,key_id,delegation_id,policy_version,time_evidence_version):
 from app.models.proof_trust import ProofTrustedKey,ProofDelegation,ProofRevocation
 key=db.get(ProofTrustedKey,key_id); delegation=db.get(ProofDelegation,delegation_id)
 if key is None or delegation is None: return None
 revs=[str(r.revocation_uuid)+":"+str(r.signature)+":"+str(r.policy_version) for r in db.scalars(__import__('sqlalchemy').select(ProofRevocation).where(ProofRevocation.target_ref==key_id)).all()]
 key_version=f"{key.key_id}:{key.state}:{key.algorithm}:{key.canonicalization_version}:{key.registered_at.isoformat()}"
 delegation_version=f"{delegation.delegation_uuid}:{delegation.state}:{delegation.policy_version}:{delegation.expires_at.isoformat()}"
 return verification_input_fingerprint(proof=proof,event_uuid=event_uuid,content_sha256=content_sha256,key_version=key_version,delegation_version=delegation_version,revocation_version='|'.join(sorted(revs)),policy_version=policy_version,time_evidence_version=time_evidence_version)

def save_verification_result(db, result, *, input_fingerprint, policy_version):
 from app.models.proof_trust import ProofVerificationResult
 from sqlalchemy import select
 existing=db.scalar(select(ProofVerificationResult).where(ProofVerificationResult.event_uuid==result.event_uuid,ProofVerificationResult.input_fingerprint==input_fingerprint))
 if existing is not None: return existing
 result.input_fingerprint=input_fingerprint; result.policy_version=policy_version; db.add(result); db.flush()
 if db.info.get('stage5a_fail_verification_before_commit'): raise RuntimeError('INJECTED_VERIFICATION_SAVE_FAILURE')
 return result

def read_current_verification(db, *, event_uuid, current_input_fingerprint):
 from app.models.proof_trust import ProofVerificationResult
 from sqlalchemy import select
 row=db.scalar(select(ProofVerificationResult).where(ProofVerificationResult.event_uuid==event_uuid,ProofVerificationResult.input_fingerprint==current_input_fingerprint).order_by(ProofVerificationResult.created_at.desc()))
 return row if row is not None else "stale_requires_reverification"
FIELDS=("event_uuid","content_sha256","clinic_uuid","entity_type","entity_uuid","operation","revision_uuid","parent_revision_uuid","origin_user_uuid","origin_device_uuid","origin_service_uuid","operation_uuid","authorization_policy_version","authorization_reference","proof_format_version","signing_key_id","issued_at")
def parse_proof_json(raw):
 def reject_duplicates(pairs):
  out={}
  for k,v in pairs:
   if k in out: raise ValueError("DUPLICATE_JSON_KEY")
   out[k]=v
  return out
 value=json.loads(raw,object_pairs_hook=reject_duplicates)
 if not isinstance(value,dict): raise ValueError("PROOF_OBJECT_REQUIRED")
 return value
def canonical_bytes(proof):
 if not isinstance(proof,dict) or any(k not in FIELDS and k!="signature" for k in proof): raise ValueError("UNSUPPORTED_PROOF_FIELD")
 allowed={k:proof[k] for k in FIELDS if k in proof}
 if any(v is not None and not isinstance(v,str) for v in allowed.values()): raise ValueError("UNSUPPORTED_PROOF_VALUE_TYPE")
 return json.dumps(allowed,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
def verify_signature(proof,public_key_b64):
 try: Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(proof["signature"]),canonical_bytes(proof)); return "valid"
 except (ValueError,KeyError,InvalidSignature): return "invalid"
def verify_binding(proof,**expected): return "valid" if all(str(proof.get(k))==str(v) for k,v in expected.items()) else "mismatch"
REQUIRED_NON_NULL=("event_uuid","content_sha256","clinic_uuid","entity_type","operation","revision_uuid","authorization_policy_version","proof_format_version","signing_key_id","issued_at","origin_user_uuid","origin_device_uuid","origin_service_uuid","operation_uuid","authorization_reference")
UUID_FIELDS=("event_uuid","clinic_uuid","entity_uuid","revision_uuid","origin_user_uuid","origin_device_uuid","operation_uuid")
def validate_required_fields(proof):
 if any(proof.get(k) in (None,"") for k in REQUIRED_NON_NULL): return "invalid"
 # Optional UUID fields (notably parent_revision_uuid on create) may be null;
 # validate their representation only when a value is present.
 if any(k in proof and proof[k] is not None and (not isinstance(proof[k],str) or not re.fullmatch(r"[0-9a-fA-F-]{36}",proof[k])) for k in UUID_FIELDS): return "invalid"
 if not re.fullmatch(r"[0-9a-fA-F]{64}",proof.get("content_sha256","")): return "invalid"
 # Local journal uses ``insert`` for a newly-created entity; it is the same
 # operation class as create and is part of the current transport contract.
 if proof.get("operation") not in {"create","insert","update","delete"}: return "invalid"
 if proof.get("operation") in {"update","delete"} and not proof.get("parent_revision_uuid"): return "invalid"
 if proof.get("parent_revision_uuid") is not None:
  try: uuid.UUID(str(proof["parent_revision_uuid"]))
  except (ValueError,TypeError): return "invalid"
 return "valid"
def verify_key_scope(proof,key,*,clinic_uuid,origin_service_uuid,origin_device_uuid,allowed_algorithms=("Ed25519",),canonicalization_version=CANONICALIZATION_VERSION):
 if key is None or key.state not in {"active","retired"}: return "unknown"
 if key.clinic_uuid != clinic_uuid or key.origin_service_uuid != origin_service_uuid or (key.origin_device_uuid is not None and key.origin_device_uuid != origin_device_uuid): return "mismatch"
 if key.algorithm not in allowed_algorithms or key.canonicalization_version != canonicalization_version or proof.get("signing_key_id") != key.key_id: return "invalid"
 return "valid"
def verify_delegation_scope(proof,delegation,*,clinic_uuid,origin_service_uuid,user_uuid,entity_type,operation,policy_version):
 if delegation is None: return "missing"
 from datetime import datetime, timezone
 if delegation.state != "active": return "revoked"
 now = datetime.now(timezone.utc)
 if delegation.expires_at <= now: return "expired"
 if delegation.clinic_uuid != clinic_uuid or delegation.origin_service_uuid != origin_service_uuid or delegation.user_uuid != user_uuid or delegation.entity_type != entity_type or delegation.operation != operation or delegation.policy_version != policy_version: return "mismatch"
 return "valid"

def evaluate_time_window(*,issued_at,evaluation_at,trusted_evidence,uncertainty_seconds=0,delegation_days=DELEGATION_DAYS):
 try:
  issued=datetime.fromisoformat(str(issued_at).replace("Z","+00:00")); now=datetime.fromisoformat(str(evaluation_at).replace("Z","+00:00"))
  if issued.tzinfo is None or now.tzinfo is None: return "time_indeterminate"
 except (TypeError,ValueError): return "time_indeterminate"
 if not isinstance(trusted_evidence,dict) or trusted_evidence.get("fixture") is not True or trusted_evidence.get("authority_verified") is not True or trusted_evidence.get("integrity_valid") is not True or not trusted_evidence.get("authority_ref") or trusted_evidence.get("proof_binding") is not True or trusted_evidence.get("freshness_valid") is not True: return "time_indeterminate"
 if trusted_evidence.get("issued_at") is not None and str(trusted_evidence.get("issued_at")) != str(issued_at): return "time_indeterminate"
 try: uncertainty=float(uncertainty_seconds)
 except (TypeError,ValueError): return "time_indeterminate"
 if uncertainty < 0: return "time_indeterminate"
 expiry=issued+timedelta(days=delegation_days)
 if now < issued: return "time_invalid_before_issue"
 if now+timedelta(seconds=uncertainty) >= expiry and now-timedelta(seconds=uncertainty) < expiry: return "time_indeterminate"
 return "time_valid" if now < expiry else "time_expired"

def evaluate_revocation_order(*,issued_at,revoked_at,order_evidence):
 if not isinstance(order_evidence,dict) or order_evidence.get("trusted") is not True: return "revocation_order_indeterminate"
 try:
  issued=datetime.fromisoformat(str(issued_at).replace("Z","+00:00")); revoked=datetime.fromisoformat(str(revoked_at).replace("Z","+00:00"))
 except (TypeError,ValueError): return "revocation_order_indeterminate"
 return "revocation_before_issue" if revoked<=issued else "revocation_after_issue"
def revocation_canonical_bytes(r):
 keys=("revocation_uuid","target_type","target_ref","reason_code","effective_at_declared","authority_key_id","policy_version","target_clinic_uuid","target_origin_service_uuid")
 return json.dumps({k:r[k] for k in keys},sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def verify_revocation_signature(r,public_key_b64):
 try: Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(r["signature"]),revocation_canonical_bytes(r)); return "valid"
 except (ValueError,KeyError,InvalidSignature): return "invalid"
def verify_revocation_authority(r,key,*,clinic_uuid,target_type,policy_version):
 if key is None or key.state != "active": return "unknown"
 if key.key_id != r.get("authority_key_id") or str(key.clinic_uuid) != str(clinic_uuid) or str(r.get("target_clinic_uuid")) != str(clinic_uuid) or (r.get("target_origin_service_uuid") is not None and str(r.get("target_origin_service_uuid")) != str(key.origin_service_uuid)) or target_type not in {"key","delegation","proof"} or r.get("target_type") != target_type or r.get("policy_version") != policy_version: return "mismatch"
 return "valid"
