import os,uuid
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.services.proof_trust_binding_service import *
from app.models.proof_trust_binding import ProofTrustBinding
from app.models.user import User
engine=create_engine(os.environ["DATABASE_URL"])
def main():
 a=uuid.uuid4(); c=uuid.uuid4(); s=uuid.uuid4(); issuer=uuid.uuid4(); key="test-binding-"+str(uuid.uuid4()); scope="clinic-chain:"+str(uuid.uuid4())
 with Session(engine) as db:
  approver=User(role="super_admin")

  row=create_local_binding(db,signing_key_id=key,issuer_uuid=issuer,revocation_authority_uuid=a,chain_scope=scope,chain_contract_version="revocation-chain-v1",clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1",approval_source="local-trust-admin:fixture",approver=approver); db.commit(); fp=binding_input_fingerprint(row); print("binding_resolved",resolve_local_binding(db,proof={"signing_key_id":key,"origin_service_uuid":str(issuer)},clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1")["status"]); assert resolve_local_binding(db,proof={"signing_key_id":key,"origin_service_uuid":str(issuer)},clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1")["input_fingerprint"]==fp
  assert resolve_local_binding(db,proof={"signing_key_id":key,"origin_service_uuid":str(issuer)},clinic_uuid=uuid.uuid4(),origin_service_uuid=s,policy_version="test-policy-v1")["reason"]=="TRUST_BINDING_MISSING"; print("scope_mismatch_blocked=1")
  assert resolve_local_binding(db,proof={"signing_key_id":"missing","origin_service_uuid":str(issuer)},clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1")["reason"]=="TRUST_BINDING_MISSING"; print("missing_blocked=1")
  row.state="revoked"; row.updated_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); db.commit(); assert resolve_local_binding(db,proof={"signing_key_id":key,"origin_service_uuid":str(issuer)},clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1")["status"]=="blocked"; print("revoked_blocked=1")
  assert binding_input_fingerprint(row)!=fp; print("binding_change_invalidates_fingerprint=1")
  try:create_local_binding(db,signing_key_id=key,issuer_uuid=issuer,revocation_authority_uuid=a,chain_scope=scope,chain_contract_version="revocation-chain-v1",clinic_uuid=c,origin_service_uuid=s,policy_version="test-policy-v1",approval_source="client-payload",approver=approver)
  except ValueError as e: print("approval_guard",e)
 with Session(engine) as db: assert db.scalar(select(func.count()).select_from(ProofTrustBinding).where(ProofTrustBinding.binding_uuid==row.binding_uuid))==1; print("new_session_persistent=1")
if __name__=="__main__":main()
