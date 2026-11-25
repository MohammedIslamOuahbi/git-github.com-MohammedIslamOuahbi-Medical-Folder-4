import base64, os, uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.models.revocation_chain_record import RevocationChainRecord
from app.services.revocation_chain_service import *
DB=os.environ["DATABASE_URL"]
engine=create_engine(DB)
def make(key,authority,scope,seq,prev,payload=None,record_uuid=None):
 x={"record_uuid":record_uuid or uuid.uuid4(),"authority_uuid":authority,"chain_scope":scope,"contract_version":"revocation-chain-v1","canonicalization_version":CHAIN_CANONICALIZATION,"sequence":seq,"previous_record_hash":prev,"record":payload or {"target_type":"key","target_ref":str(uuid.uuid4()),"reason":"test"}}
 x["record_hash"]=record_hash(x); x["signature"]=base64.b64encode(key.sign(record_bytes(x))).decode(); return x
def put(x,pub,fail=False):
 with Session(engine) as s:
  if fail:s.info["revocation_chain_fail_after_insert"]=True
  try:r=store_chain_record(s,x,authority_public_key=pub); rid=r.record_uuid; s.commit(); return type('R',(),{'record_uuid':rid})()
  except Exception: s.rollback(); raise
def count(scope,a):
 with Session(engine) as s:return s.scalar(select(func.count()).select_from(RevocationChainRecord).where(RevocationChainRecord.authority_uuid==a,RevocationChainRecord.chain_scope==scope))
def main():
 key=Ed25519PrivateKey.generate(); pub=base64.b64encode(key.public_key().public_bytes_raw()).decode(); a=uuid.uuid4(); scope='clinic:test-chain:'+str(uuid.uuid4()); r1=make(key,a,scope,1,GENESIS_RECORD_HASH); r2=make(key,a,scope,2,r1['record_hash']); r3=make(key,a,scope,3,r2['record_hash'])
 put(r2,pub); put(r1,pub); put(r3,pub)
 with Session(engine) as s: out=check_coverage(s,authority_uuid=a,chain_scope=scope,checkpoint_sequence=3,checkpoint_hash=r3['record_hash']); assert out['status']=='complete'; print('complete_out_of_order',out)
 assert put(r1,pub).record_uuid == r1['record_uuid']; print('idempotent',count(scope,a))
 bad=dict(r2); bad['signature']=base64.b64encode(Ed25519PrivateKey.generate().sign(record_bytes(bad))).decode()
 try:put(bad,pub); assert False
 except ValueError as e: print('invalid_signature',e)
 rconf=make(key,a,scope,2,r1['record_hash'],record_uuid=uuid.uuid4())
 try:put(rconf,pub); assert False
 except ValueError as e: print('sequence_conflict',e)
 with Session(engine) as s: out=check_coverage(s,authority_uuid=a,chain_scope=scope,checkpoint_sequence=3,checkpoint_hash='f'*64); assert out['status']=='conflicting'; print('checkpoint_mismatch',out)
 a2=uuid.uuid4(); sc2='gap:'+str(uuid.uuid4()); g1=make(key,a2,sc2,1,GENESIS_RECORD_HASH); g2=make(key,a2,sc2,2,g1['record_hash']); g3=make(key,a2,sc2,3,g2['record_hash']); put(g1,pub); put(g3,pub)
 with Session(engine) as s: out=check_coverage(s,authority_uuid=a2,chain_scope=sc2,checkpoint_sequence=3,checkpoint_hash=g3['record_hash']); assert out['status']=='incomplete'; print('gap',out)
 put(g2,pub)
 with Session(engine) as s: out=check_coverage(s,authority_uuid=a2,chain_scope=sc2,checkpoint_sequence=3,checkpoint_hash=g3['record_hash']); assert out['status']=='complete'; print('gap_filled',out)
 a3=uuid.uuid4(); sc3='rollback:'+str(uuid.uuid4()); z=make(key,a3,sc3,1,GENESIS_RECORD_HASH)
 try:put(z,pub,True); assert False
 except RuntimeError as e: print('rollback',e)
 assert count(sc3,a3)==0
 with Session(engine) as s: out=check_coverage(s,authority_uuid=a3,chain_scope=sc3,checkpoint_sequence=1,checkpoint_hash=z['record_hash']); assert out['status']=='incomplete'; print('rollback_persisted',out)
if __name__=='__main__':main()
