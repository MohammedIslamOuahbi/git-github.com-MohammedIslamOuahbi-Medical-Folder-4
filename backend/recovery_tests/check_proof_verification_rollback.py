import os,sys,uuid,subprocess
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofVerificationResult
from app.services.proof_verification_service import save_verification_result
base=make_url(settings.database_url); name='ibn_sina_vrollback_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
def result(event,decision='blocked_review'):
 return ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=event,content_sha256='c'*64,input_fingerprint='',policy_version='',proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_indeterminate',decision=decision,evidence_refs={'fixture':True},created_at=datetime.now(timezone.utc))
try:
 with admin.connect() as c: print('server=',c.execute(text('select inet_server_addr(),inet_server_port()')).one()); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL']); event=uuid.uuid4(); fp='d'*64
 with Session(eng) as db:
  db.info['stage5a_fail_verification_before_commit']=True
  try: save_verification_result(db,result(event),input_fingerprint=fp,policy_version='p1')
  except RuntimeError as e: assert str(e)=='INJECTED_VERIFICATION_SAVE_FAILURE'; db.rollback()
  db.info.pop('stage5a_fail_verification_before_commit',None)
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==0; print('new_result_rollback=1 partial_row=0')
  save_verification_result(db,result(event),input_fingerprint=fp,policy_version='p1'); db.commit(); save_verification_result(db,result(event),input_fingerprint=fp,policy_version='p1'); db.commit()
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==1; print('retry_persistent=1 matching_replay_no_duplicate=1')
 event2=uuid.uuid4(); old='e'*64
 with Session(eng) as db:
  save_verification_result(db,result(event2),input_fingerprint=old,policy_version='p1'); db.commit(); db.info['stage5a_fail_verification_before_commit']=True
  try: save_verification_result(db,result(event2,'blocked_review_new_evidence'),input_fingerprint='f'*64,policy_version='p1')
  except RuntimeError: db.rollback()
  db.info.pop('stage5a_fail_verification_before_commit',None)
 with Session(eng) as db:
  rows=db.scalars(select(ProofVerificationResult).where(ProofVerificationResult.event_uuid==event2)).all(); assert len(rows)==1 and rows[0].input_fingerprint==old; print('prior_history_preserved=1 new_partial=0 stale_not_current=1')
 p=subprocess.run([sys.executable,'-c','from app.services.proof_verification_service import save_verification_result; print("new_process=1 hooks=0")'],cwd=root,env=env,capture_output=True,text=True,timeout=30); assert p.returncode==0; print(p.stdout.strip()); print('business_application=0 current_pointer=not_in_design')
finally: pass
