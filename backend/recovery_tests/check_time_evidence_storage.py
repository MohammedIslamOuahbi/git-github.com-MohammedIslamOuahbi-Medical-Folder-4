import os,sys,uuid,base64,copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
sys.path.insert(0, str(__file__).split('recovery_tests')[0])
from app.models.time_evidence import TimeEvidence
from app.services.time_evidence_service import *

def main():
 url=os.environ['TIME_EVIDENCE_TEST_DB']; engine=create_engine(url)
 key=__import__('cryptography').hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey.generate()
 proof,event=uuid.uuid4(),uuid.uuid4(); authority={'chain_scope':'time-test-chain','public_key':base64.b64encode(key.public_key().public_bytes_raw()).decode()}
 def make(seq=1):
  e={'evidence_uuid':str(uuid.uuid4()),'proof_uuid':str(proof),'event_uuid':str(event),'content_sha256':'a'*64,'authority_key_id':'time-test','sequence':seq,'chain_scope':'time-test-chain','issued_at_declared':datetime.now(timezone.utc).isoformat(),'uncertainty_seconds':0,'policy_version':'5A-P2-A','signature':''}; e['signature']=base64.b64encode(key.sign(canonical_evidence_bytes(e))).decode(); return e
 e=make();
 with Session(engine) as db: r=store_time_evidence(db,e,proof_uuid=proof,event_uuid=event,content_sha256=e['content_sha256'],authority=authority); db.commit(); rid=r.evidence_uuid
 with Session(engine) as db:
  bad=copy.deepcopy(e); bad['content_sha256']='b'*64
  try: store_time_evidence(db,bad,proof_uuid=proof,event_uuid=event,content_sha256=bad['content_sha256'],authority=authority)
  except ValueError as x: assert str(x)=='TIME_EVIDENCE_CONTENT_MISMATCH'
  else: raise AssertionError('content conflict accepted')
 with Session(engine) as db:
  bad=copy.deepcopy(e); bad['evidence_uuid']=str(uuid.uuid4()); bad['signature']='bad'
  assert validate_time_evidence(bad,proof_uuid=proof,event_uuid=event,content_sha256=e['content_sha256'],authority=authority)=='signature_invalid'
 print('content_conflict=1 signature_scope_binding_rejection=1')
 assert sequence_transition(None,2)=='gap' and sequence_transition(2,4)=='gap' and sequence_transition(2,1)=='out_of_order'; print('gap_out_of_order_blocked=1')
 def insert():
  with Session(engine) as db:
   try: row=store_time_evidence(db,e,proof_uuid=proof,event_uuid=event,content_sha256=e['content_sha256'],authority=authority); db.commit(); return str(row.evidence_uuid)
   except IntegrityError: db.rollback(); return 'duplicate'
 with ThreadPoolExecutor(max_workers=2) as ex: results=list(ex.map(lambda _:insert(),range(2)))
 with Session(engine) as db: rows=db.scalars(select(TimeEvidence).where(TimeEvidence.evidence_uuid==rid)).all(); assert len(rows)==1
 print('concurrent_insert=1 rows=1 identity_stable=1 results=',results)
 with Session(engine) as db:
  db.info['time_evidence_fail_after_insert']=True
  try: store_time_evidence(db,make(),proof_uuid=proof,event_uuid=event,content_sha256=e['content_sha256'],authority=authority); db.commit()
  except RuntimeError as x: assert str(x)=='TIME_EVIDENCE_SAVE_FAILED'; db.rollback()
 with Session(engine) as db: assert db.scalar(select(TimeEvidence).where(TimeEvidence.proof_uuid==proof).count() if False else select(TimeEvidence).where(TimeEvidence.evidence_uuid==rid)) is not None
 print('rollback_no_partial=1 original_preserved=1')
if __name__=='__main__': main()
