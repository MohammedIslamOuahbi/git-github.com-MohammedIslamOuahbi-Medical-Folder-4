import hashlib, json, uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.proof_trust_binding import ProofTrustBinding

def binding_input_fingerprint(binding):
    data={k:str(getattr(binding,k)) for k in ("binding_uuid","signing_key_id","issuer_uuid","revocation_authority_uuid","chain_scope","chain_contract_version","clinic_uuid","origin_service_uuid","policy_version","state","binding_version")}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def create_local_binding(db, *, signing_key_id, issuer_uuid, revocation_authority_uuid, chain_scope, chain_contract_version, clinic_uuid, origin_service_uuid, policy_version, approval_source, approved_by=None, approver=None):
    from app.core.permissions import user_has_permission
    if approver is None or not user_has_permission(approver, "users.edit_permissions"):
        raise PermissionError("TRUST_BINDING_PERMISSION_REQUIRED")
    if not approval_source or not approval_source.startswith("local-trust-admin:"):
        raise ValueError("TRUST_BINDING_APPROVAL_REQUIRED")
    row=ProofTrustBinding(binding_uuid=uuid.uuid4(),signing_key_id=signing_key_id,issuer_uuid=issuer_uuid,revocation_authority_uuid=revocation_authority_uuid,chain_scope=chain_scope,chain_contract_version=chain_contract_version,clinic_uuid=clinic_uuid,origin_service_uuid=origin_service_uuid,policy_version=policy_version,state="active",binding_version=1,approval_source=approval_source,approved_by=approved_by,created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc))
    db.add(row); db.flush(); return row

def resolve_local_binding(db, *, proof, clinic_uuid, origin_service_uuid, policy_version):
    key=proof.get("signing_key_id"); issuer=proof.get("origin_service_uuid")
    rows=db.scalars(select(ProofTrustBinding).where(ProofTrustBinding.signing_key_id==key,ProofTrustBinding.clinic_uuid==clinic_uuid,ProofTrustBinding.origin_service_uuid==origin_service_uuid,ProofTrustBinding.policy_version==policy_version)).all()
    active=[r for r in rows if r.state=="active" and (r.issuer_uuid is None or str(r.issuer_uuid)==str(issuer))]
    if not rows: return {"status":"blocked","reason":"TRUST_BINDING_MISSING","input_fingerprint":None}
    if len(active)!=1: return {"status":"blocked","reason":"TRUST_BINDING_AMBIGUOUS_OR_REVOKED","input_fingerprint":None}
    row=active[0]
    return {"status":"resolved","binding":row,"chain_scope":row.chain_scope,"chain_contract_version":row.chain_contract_version,"revocation_authority_uuid":str(row.revocation_authority_uuid),"input_fingerprint":binding_input_fingerprint(row)}
