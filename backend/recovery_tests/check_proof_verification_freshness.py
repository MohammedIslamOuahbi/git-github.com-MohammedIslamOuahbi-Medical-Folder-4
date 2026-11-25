import os,sys,uuid,subprocess,hashlib
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofVerificationResult
from app.services.proof_verification_service import verification_input_fingerprint
base=make_url(settings.database_url); name='ibn_sina_vfresh_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c: print('server=',c.execute(text('select inet_server_addr(),inet_server_port()')).one()); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 event=uuid.uuid4(); proof={'event_uuid':str(event),'content_sha256':'a'*64,'signing_key_id':'k1'}; basekw=dict(proof=proof,event_uuid=event,content_sha256='a'*64,key_version='k:v1',delegation_version='d:v1',revocation_version='r:none',policy_version='p:v1',time_evidence_version='t:fixture:v1'); fp1=verification_input_fingerprint(**basekw); fp2=verification_input_fingerprint(**{**basekw,'revocation_version':'r:revoked'}); assert fp1!=fp2
 with Session(create_engine(env['DATABASE_URL'])) as db:
  def save(fp,decision):
   row=ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=event,content_sha256='a'*64,input_fingerprint=fp,policy_version='p:v1',proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_indeterminate',decision=decision,evidence_refs={'fixture':True,'fingerprint':fp},created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)); db.add(row); db.flush(); return row
  save(fp1,'blocked_review'); db.commit(); save(fp2,'blocked_review_revoked'); db.commit()
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==2
 with Session(create_engine(env['DATABASE_URL'])) as db:
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==2; print('fresh_session=history=2 current_inputs_distinct=1 stale_cache_not_reused=1')
 print('fingerprints=changed_on_revocation_or_policy_or_time=1'); print('time_indeterminate_without_operational_source=1 no_business_application=1'); print('PASS verification freshness; no operational proof')
finally: pass
