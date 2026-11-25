import os,sys,uuid,subprocess
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofVerificationResult
from app.services.proof_verification_service import evaluate_time_window,evaluate_revocation_order
base=make_url(settings.database_url); name='ibn_sina_time_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c:
  ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 issued='2026-10-14T00:00:00+00:00'; trusted={'fixture':True,'authority_verified':True,'integrity_valid':True,'freshness_valid':True,'authority_ref':'fixture-time-authority','proof_binding':True,'issued_at':issued}; cases=[('before', '2026-10-13T23:59:59+00:00',0,'time_invalid_before_issue'),('valid', '2026-10-14T12:00:00+00:00',0,'time_valid'),('boundary','2026-10-21T00:00:00+00:00',0,'time_expired'),('after','2026-10-21T00:00:01+00:00',0,'time_expired'),('uncertain','2026-10-20T23:59:59+00:00',2,'time_indeterminate'),('local_clock_no_evidence','2026-10-15T00:00:00+00:00',0,'time_indeterminate'),('unknown_authority','2026-10-15T00:00:00+00:00',0,'time_indeterminate')]
 results=[]
 for label,at,unc,expected in cases:
  evidence={} if label in {'local_clock_no_evidence','unknown_authority'} else trusted
  got=evaluate_time_window(issued_at=issued,evaluation_at=at,trusted_evidence=evidence,uncertainty_seconds=unc); assert got==expected; results.append((label,got))
 assert evaluate_revocation_order(issued_at=issued,revoked_at='2026-10-13T00:00:00+00:00',order_evidence={})=='revocation_order_indeterminate'
 assert evaluate_revocation_order(issued_at=issued,revoked_at='2026-10-13T00:00:00+00:00',order_evidence={'trusted':True})=='revocation_before_issue'
 assert evaluate_revocation_order(issued_at=issued,revoked_at='2026-10-15T00:00:00+00:00',order_evidence={'trusted':True})=='revocation_after_issue'
 assert evaluate_time_window(issued_at=issued,evaluation_at='2026-10-15T00:00:00+00:00',trusted_evidence=dict(trusted,integrity_valid=False))=='time_indeterminate'
 assert evaluate_time_window(issued_at=issued,evaluation_at='2026-10-15T00:00:00+00:00',trusted_evidence=dict(trusted,issued_at='2026-10-13T00:00:00+00:00'))=='time_indeterminate'
 assert evaluate_time_window(issued_at=issued,evaluation_at='2026-10-22T00:00:00+00:00',trusted_evidence=trusted)=='time_expired'
 with Session(create_engine(env['DATABASE_URL'])) as db:
  row=ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=uuid.uuid4(),content_sha256='a'*64,proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_indeterminate',decision='blocked_review',evidence_refs={'synthetic':True,'policy_days':7},created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)); db.add(row); db.commit()
  db.expire_all(); assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==1
 print('cases=',results); print('revocation_order=before_after_indeterminate'); print('fresh_session=persistent=1 policy_days=7 decision=blocked_review business_application=0'); print('PASS time policy; no operational proof')
finally: pass

