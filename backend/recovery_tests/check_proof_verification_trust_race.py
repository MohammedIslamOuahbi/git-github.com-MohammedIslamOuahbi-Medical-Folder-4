import os,sys,uuid,subprocess,threading,base64
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofVerificationResult,ProofTrustedKey
from app.services.proof_verification_service import verification_input_fingerprint,save_verification_result,read_current_verification,revocation_canonical_bytes
from app.services.proof_revocation_service import register_revocation
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
base=make_url(settings.database_url); name='ibn_sina_vrace_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
def row(event,fp,decision): return ProofVerificationResult(verification_uuid=uuid.uuid4(),event_uuid=event,content_sha256='f'*64,input_fingerprint='',policy_version='p1',proof_format_version='1',signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_indeterminate',decision=decision,evidence_refs={'fixture':True},created_at=datetime.now(timezone.utc))
try:
 with admin.connect() as c: print('server=',c.execute(text('select inet_server_addr(),inet_server_port()')).one()); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL'],pool_size=4); event=uuid.uuid4(); proof={'event_uuid':str(event),'content_sha256':'f'*64}; clinic=uuid.uuid4(); service=uuid.uuid4(); auth='auth-'+uuid.uuid4().hex[:8]; target='target-'+uuid.uuid4().hex[:8]; key=Ed25519PrivateKey.generate(); now=datetime.now(timezone.utc); pub=base64.b64encode(key.public_key().public_bytes_raw()).decode()
 with Session(eng) as db: db.add_all([ProofTrustedKey(key_id=auth,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=None,registration_authority_uuid=uuid.uuid4(),public_key=pub,algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now),ProofTrustedKey(key_id=target,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=None,registration_authority_uuid=uuid.uuid4(),public_key=pub,algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now)]); db.commit()
 oldfp=verification_input_fingerprint(proof=proof,event_uuid=event,content_sha256='f'*64,key_version='k1',delegation_version='d1',revocation_version='r0',policy_version='p1',time_evidence_version='t0'); newfp=None;
 with Session(eng) as db: save_verification_result(db,row(event,oldfp,'blocked_review'),input_fingerprint=oldfp,policy_version='p1'); db.commit()
 gate=threading.Barrier(2); committed=threading.Event(); order=[]; result={}
 def old_check():
  with Session(eng) as db:
   order.append('old_read_fingerprint'); gate.wait(timeout=10); committed.wait(timeout=10); order.append('old_resumed'); result['old']=read_current_verification(db,event_uuid=event,current_input_fingerprint=newfp)
 def new_check():
  gate.wait(timeout=10); order.append('revocation_registration_start');
  with Session(eng) as db: rec={'revocation_uuid':str(uuid.uuid4()),'target_type':'key','target_ref':target,'reason_code':'compromise','effective_at_declared':'2026-10-14T00:00:00Z','authority_key_id':auth,'policy_version':'p1','target_clinic_uuid':str(clinic),'target_origin_service_uuid':str(service),'canonicalization_version':'deterministic-json-restricted-v1','authority_ref':'fixture'}; rec['signature']=base64.b64encode(key.sign(revocation_canonical_bytes(rec))).decode(); register_revocation(db,rec,clinic_uuid=clinic,target_type='key',policy_version='p1'); db.commit(); order.append('revocation_commit'); committed.set(); newfp=verification_input_fingerprint(proof=proof,event_uuid=event,content_sha256='f'*64,key_version='k1',delegation_version='d1',revocation_version=rec['revocation_uuid']+':'+rec['signature'],policy_version='p1',time_evidence_version='t0'); save_verification_result(db,row(event,newfp,'blocked_review'),input_fingerprint=newfp,policy_version='p1'); db.commit(); result['newfp']=newfp; result['new']='committed'
 a=threading.Thread(target=old_check); b=threading.Thread(target=new_check); a.start(); b.start(); a.join(15); b.join(15); print('raw=',order,result); assert result.get('new')=='committed' and getattr(result.get('old'),'input_fingerprint',None)==newfp; print('order=',order,'backend_connections=2 overlap=1 old_result=stale_requires_reverification new_result=committed')
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(ProofVerificationResult))==2; assert read_current_verification(db,event_uuid=event,current_input_fingerprint=result['newfp']).input_fingerprint==result['newfp']; print('fresh_session=history_preserved=1 current_matches_new_evidence=1 time_indeterminate=1 business_application=0')
finally: pass










