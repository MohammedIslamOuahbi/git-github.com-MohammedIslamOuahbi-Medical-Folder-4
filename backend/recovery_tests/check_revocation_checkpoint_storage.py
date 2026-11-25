import os,sys,uuid,base64,copy
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'backend'); from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine,select; from sqlalchemy.orm import Session
from app.models.revocation_checkpoint import RevocationCheckpoint
from app.services.revocation_checkpoint_service import *
url=os.environ['DATABASE_URL']; k=Ed25519PrivateKey.generate(); pub=base64.b64encode(k.public_key().public_bytes_raw()).decode(); a,d=uuid.uuid4(),uuid.uuid4()
def make(seq,h='a'*64,cid=None):
 x={'checkpoint_uuid':str(cid or uuid.uuid4()),'authority_uuid':str(a),'authority_key_id':'test','chain_scope':'scope-test','contract_version':'1','policy_version':'p','covered_sequence':seq,'covered_chain_hash':h,'challenge':'c-'+str(seq),'destination_device_uuid':str(d)}; x['signature']=base64.b64encode(k.sign(canonical_checkpoint_bytes(x))).decode(); return x
def put(x,fail=False):
 with Session(create_engine(url)) as db:
  if fail: db.info['checkpoint_fail_after_insert']=True
  try: r=store_checkpoint(db,x,public_key=pub); db.commit(); return ('ok',str(r.checkpoint_uuid))
  except Exception as e: db.rollback(); return (type(e).__name__,str(e))
x1=make(10); assert put(x1)[0]=='ok'; mod=copy.deepcopy(x1); mod['policy_version']='changed'; assert put(mod)[0]=='ValueError'; print('modified_unsigned_rejected=1'); conf=make(10,'b'*64,uuid.UUID(x1['checkpoint_uuid'])); assert put(conf)[0]=='ValueError'; print('same_identity_conflict=1'); old=make(5); assert put(old)[0]=='ok';
with Session(create_engine(url)) as db: cur=db.scalar(select(RevocationCheckpoint).where(RevocationCheckpoint.authority_uuid==a,RevocationCheckpoint.chain_scope=='scope-test',RevocationCheckpoint.is_current.is_(True))); assert cur.covered_sequence==10
print('older_history_preserved_pointer_stable=1'); same=make(10,'c'*64); assert put(same)[0]=='ValueError'; print('same_sequence_hash_conflict=1')
with ThreadPoolExecutor(2) as ex: rr=list(ex.map(put,[make(20),make(21)]))
with Session(create_engine(url)) as db: cur=db.scalar(select(RevocationCheckpoint).where(RevocationCheckpoint.authority_uuid==a,RevocationCheckpoint.chain_scope=='scope-test',RevocationCheckpoint.is_current.is_(True))); assert cur.covered_sequence==21
print('concurrent_updates=1 latest=21'); dup=make(30); list(ThreadPoolExecutor(2).map(put,[dup,dup]));
with Session(create_engine(url)) as db: assert len(db.scalars(select(RevocationCheckpoint).where(RevocationCheckpoint.checkpoint_uuid==uuid.UUID(dup['checkpoint_uuid']))).all())==1
print('concurrent_same=1 rows=1'); fail=make(40); assert put(fail,True)[0]=='RuntimeError';
with Session(create_engine(url)) as db: assert db.scalar(select(RevocationCheckpoint).where(RevocationCheckpoint.checkpoint_uuid==uuid.UUID(fail['checkpoint_uuid']))) is None
print('rollback=1 no_partial=1')
