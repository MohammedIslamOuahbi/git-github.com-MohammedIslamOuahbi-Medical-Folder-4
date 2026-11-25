import os,base64,uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.services.revocation_chain_service import *
from app.services.revocation_checkpoint_service import *
from app.services.origin_proof_reconciliation_queue import choose_checkpoint
from app.models.proof_trust_binding import ProofTrustBinding
from datetime import datetime,timezone
engine=create_engine(os.environ["DATABASE_URL"])
def main():
 k=Ed25519PrivateKey.generate(); pub=base64.b64encode(k.public_key().public_bytes_raw()).decode(); a=uuid.uuid4(); sc='sel:'+str(uuid.uuid4()); x={"record_uuid":uuid.uuid4(),"authority_uuid":a,"chain_scope":sc,"contract_version":"revocation-chain-v1","canonicalization_version":CHAIN_CANONICALIZATION,"sequence":1,"previous_record_hash":GENESIS_RECORD_HASH,"record":{"n":1}}; x["record_hash"]=record_hash(x); x["signature"]=base64.b64encode(k.sign(record_bytes(x))).decode()
 with Session(engine) as s:
  store_chain_record(s,x,authority_public_key=pub); s.commit(); b=ProofTrustBinding(binding_uuid=uuid.uuid4(),signing_key_id='k',issuer_uuid=None,revocation_authority_uuid=a,chain_scope=sc,chain_contract_version='revocation-chain-v1',clinic_uuid=uuid.uuid4(),origin_service_uuid=uuid.uuid4(),policy_version='p1',state='active',binding_version=1,approval_source='local-trust-admin:test',created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc)); s.add(b); s.commit(); cp={"checkpoint_uuid":str(uuid.uuid4()),"authority_uuid":str(a),"authority_key_id":"test","chain_scope":sc,"contract_version":"revocation-chain-v1","policy_version":"p1","covered_sequence":1,"covered_chain_hash":x["record_hash"],"challenge":"c","destination_device_uuid":str(uuid.uuid4())}; cp["signature"]=base64.b64encode(k.sign(canonical_checkpoint_bytes(cp))).decode(); store_checkpoint(s,cp,public_key=pub); s.commit(); out=choose_checkpoint(s,binding=b,authority_public_key=pub); assert out['status']=='resolved'; print('checkpoint_selected_by_binding=1'); b.state='revoked'; s.commit(); assert choose_checkpoint(s,binding=b,authority_public_key=pub)['status']=='blocked'; print('revoked_binding_blocked=1')
if __name__=='__main__':main()
