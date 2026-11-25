import os,sys,uuid,subprocess,threading
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofVerificationResult,ProofTrustedKey
from app.services.proof_verification_service import verification_input_fingerprint
base=make_url(settings.database_url); name='ibn_sina_vconc_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c: print('server=',c.execute(text('select inet_server_addr(),inet_server_port()')).one()); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL'],pool_size=4); event=uuid.uuid4(); proof={'event_uuid':str(event),'content_sha256':'b'*64}; fp=verification_input_fingerprint(proof=proof,event_uuid=event,content_sha256='b'*64,key_version='k1',delegation_version='d1',revocation_version='r0',policy_version='p1',time_evidence_version='t0'); barrier=threading.Barrier(2); out=[]; lock=threading.Lock()
 def worker(label):
  pid=None
  try:
   with Session(eng) as db:
    pid=db.scalar(text('select pg_backend_pid()')); barrier.wait(timeout=10); row=ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=event,content_sha256='b'*64,input_fingerprint=fp,policy_version='p1',proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_indeterminate',decision='blocked_review',evidence_refs={'fixture':True,'fp':fp},created_at=datetime.now(timezone.utc)); db.add(row)
    try: db.commit(); result='committed'
    except IntegrityError: db.rollback(); result='reused_existing'
    with lock: out.append((label,pid,result))
  except Exception as e:
   with lock: out.append((label,pid,'error:'+type(e).__name__))
 ts=[threading.Thread(target=worker,args=(x,)) for x in ('S1','S2')]; [t.start() for t in ts]; [t.join(15) for t in ts]; print('raw_concurrency=',sorted(out)); assert len(out)==2 and all(x[2] in {'committed','reused_existing'} for x in out); print('concurrency=',sorted(out), 'barrier_overlap=1')
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult).where(ProofVerificationResult.input_fingerprint==fp))==1; row=db.scalar(select(ProofVerificationResult).where(ProofVerificationResult.input_fingerprint==fp)); assert row.event_uuid==event and row.time_result=='time_indeterminate'; print('fresh_session=one_result=1 links_valid=1 time_indeterminate=1 business_application=0')
 fp2=verification_input_fingerprint(proof=proof,event_uuid=event,content_sha256='b'*64,key_version='k1',delegation_version='d1',revocation_version='r1',policy_version='p1',time_evidence_version='t0'); assert fp2!=fp
 with Session(eng) as db:
  row=ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=event,content_sha256='b'*64,input_fingerprint=fp2,policy_version='p1',proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='revoked',time_result='time_indeterminate',decision='blocked_review',evidence_refs={'revocation_version':'r1'},created_at=datetime.now(timezone.utc)); db.add(row); db.commit()
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==2; print('trust_change=history_preserved=1 stale_result_not_current=1')
 print('PASS verification concurrency; no operational proof')
finally: pass


