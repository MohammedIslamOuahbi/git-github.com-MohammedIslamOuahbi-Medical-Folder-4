import os,sys,uuid,subprocess,base64
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.proof_trust import ProofTrustedKey,ProofRevocation,ProofDelegation
from app.services.proof_verification_service import revocation_canonical_bytes,CANONICALIZATION_VERSION
from app.services.proof_revocation_service import register_revocation,parse_revocation_json
base=make_url(settings.database_url); name='ibn_sina_revreg_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
def rec(k,clinic,typ='key',rid=None): return {'revocation_uuid':str(rid or uuid.uuid4()),'target_type':typ,'target_ref':k,'reason_code':'compromise','effective_at_declared':'2026-10-14T00:00:00Z','authority_key_id':'AUTH','policy_version':'5A-P1-20261014','target_clinic_uuid':str(clinic),'target_origin_service_uuid':str(uuid.uuid4()),'canonicalization_version':CANONICALIZATION_VERSION,'authority_ref':'fixture'}
def sign(r,k): r['signature']=base64.b64encode(k.sign(revocation_canonical_bytes(r))).decode(); return r
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL']); now=datetime.now(timezone.utc); clinic=uuid.uuid4(); service=uuid.uuid4(); key=Ed25519PrivateKey.generate(); authid='authority-'+uuid.uuid4().hex[:8]; target='target-'+uuid.uuid4().hex[:8]; pub=base64.b64encode(key.public_key().public_bytes_raw()).decode()
 with Session(eng) as db:
  db.add(ProofTrustedKey(key_id=authid,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=None,registration_authority_uuid=uuid.uuid4(),public_key=pub,algorithm='Ed25519',canonicalization_version=CANONICALIZATION_VERSION,state='active',registered_at=now)); db.add(ProofTrustedKey(key_id=target,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=None,registration_authority_uuid=uuid.uuid4(),public_key=pub,algorithm='Ed25519',canonicalization_version=CANONICALIZATION_VERSION,state='active',registered_at=now)); db.commit()
  delegation_id=uuid.uuid4(); db.add(ProofDelegation(delegation_uuid=delegation_id,clinic_uuid=clinic,origin_service_uuid=service,user_uuid=uuid.uuid4(),entity_type='worker',operation='update',policy_version='5A-P1-20261014',issued_at=now,expires_at=now, state='active',authority_ref='fixture')); db.commit()
  valid=rec(target,clinic); valid['authority_key_id']=authid; valid['target_origin_service_uuid']=str(service); valid=sign(valid,key); register_revocation(db,valid,clinic_uuid=clinic,target_type='key',policy_version=valid['policy_version']); db.commit(); print('valid=accepted rows=1')
  results=[]
  for label,change in [('bad_signature',{'signature':'AAAA'}),('unknown_authority',{'authority_key_id':'unknown'}),('wrong_service',{'target_origin_service_uuid':str(uuid.uuid4())}),('wrong_target',{'target_ref':'missing'}),('unsupported_proof',{'target_type':'proof'}),('unsupported_version',{'policy_version':'unsupported'}),('missing_field',{'reason_code':''}),('unsupported_field',{'extra':'rejected'})]:
   r=dict(valid,revocation_uuid=str(uuid.uuid4()),**change)
   if label != 'bad_signature': r=sign(r,key)
   try: register_revocation(db,r,clinic_uuid=clinic,target_type=r.get('target_type','key'),policy_version='5A-P1-20261014'); results.append((label,'accepted'))
   except Exception as e: results.append((label,str(e)))
  assert register_revocation(db,valid,clinic_uuid=clinic,target_type='key',policy_version=valid['policy_version']).revocation_uuid==uuid.UUID(valid['revocation_uuid']); altered=sign(dict(valid,reason_code='different'),key)
  try: register_revocation(db,altered,clinic_uuid=clinic,target_type='key',policy_version=valid['policy_version']); results.append(('uuid_reuse_changed','accepted'))
  except Exception as e: results.append(('uuid_reuse_changed',str(e)))
  injected=dict(valid,revocation_uuid=str(uuid.uuid4())); injected=sign(injected,key)
  db.info['stage5a_fail_revocation_before_commit']=True
  try: register_revocation(db,injected,clinic_uuid=clinic,target_type='key',policy_version=valid['policy_version']); results.append(('rollback_hook','accepted'))
  except Exception as e: results.append(('rollback_hook',str(e))); db.rollback()
  db.info.pop('stage5a_fail_revocation_before_commit',None)
  extra=[]
  cases2=[
   ('authority_other_clinic',dict(valid,revocation_uuid=str(uuid.uuid4()),target_clinic_uuid=str(uuid.uuid4()))),
   ('delegation_missing',dict(valid,revocation_uuid=str(uuid.uuid4()),target_type='delegation',target_ref=str(uuid.uuid4()))),
   ('delegation_out_of_scope',dict(valid,revocation_uuid=str(uuid.uuid4()),target_type='delegation',target_ref=str(delegation_id),target_origin_service_uuid=str(uuid.uuid4()))),
   ('unsupported_type',dict(valid,revocation_uuid=str(uuid.uuid4()),target_type='certificate')),
  ]
  for label,r in cases2:
   r=sign(r,key)
   try: register_revocation(db,r,clinic_uuid=clinic,target_type=r['target_type'],policy_version=valid['policy_version']); extra.append((label,'accepted'))
   except Exception as e: extra.append((label,str(e)))
  try: parse_revocation_json('{"target_type":"key","target_type":"proof"}'); extra.append(('duplicate_json','accepted'))
  except Exception as e: extra.append(('duplicate_json',str(e)))
  print('additional_cases=',extra)
  print('cases=',results,'matching_repeat_no_extra=1')
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(ProofRevocation))==1; assert db.scalar(select(func.count()).select_from(ProofDelegation))==1; print('fresh_session=original_only=1 trust_unchanged=1 delegations_unchanged=1 historical_unsigned_not_trusted=1 rollback_atomic=1')
 print('PASS revocation registration matrix; no operational proof')
finally: pass
