"""Isolated issuer -> verifier -> eligibility proof; no business application."""
import os,sys,uuid,base64,subprocess,threading
from pathlib import Path
from datetime import datetime,timezone,timedelta
from sqlalchemy import create_engine,select,text,func
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.sync_change import SyncChange
from app.models.proof_pending import OriginProofRequest
from app.models.proof_trust import ProofTrustedKey,ProofDelegation
from app.models.origin_proof import OriginProof
from app.services.proof_issuer_service import ProofIssuerService,MemoryKeyProvider
from app.services.proof_verification_service import validate_required_fields,verify_signature,verify_binding,verify_key_scope,verify_delegation_scope
from app.services.application_eligibility_service import evaluate_application_eligibility
dburl=os.environ.get('STAGE5_ENTITY_DB')
if not dburl or 'demo' in dburl.lower() or 'clinic' in dburl.lower(): raise SystemExit('isolated STAGE5_ENTITY_DB required')
eng=create_engine(dburl); root=Path(__file__).resolve().parents[1]
with eng.connect() as c:
 name,=c.execute(text('select current_database()')).one()
 cur=subprocess.run([sys.executable,'-m','alembic','current'],cwd=root,env={**os.environ,'DATABASE_URL':dburl},capture_output=True,text=True).stdout
 assert '20261008_24' in cur
print(f'database={name} head=20261008_24')
now=datetime.now(timezone.utc); clinic=uuid.uuid4(); service=uuid.uuid4(); device=uuid.uuid4(); user=uuid.uuid4(); entity=uuid.uuid4(); rev=uuid.uuid4(); op=uuid.uuid4(); event=uuid.uuid4(); kid='issuer-fixture-'+uuid.uuid4().hex[:8]; dg=uuid.uuid4(); priv=Ed25519PrivateKey.generate(); pub=base64.b64encode(priv.public_key().public_bytes_raw()).decode()
with Session(eng) as db:
 db.add(ProofTrustedKey(key_id=kid,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=device,registration_authority_uuid=uuid.uuid4(),public_key=pub,algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now))
 db.add(ProofDelegation(delegation_uuid=dg,clinic_uuid=clinic,origin_service_uuid=service,user_uuid=user,entity_type='workers',operation='create',policy_version='5A-P1-20261014',issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(days=7),state='active',authority_ref='fixture-authority'))
 db.add(SyncChange(change_uuid=event,revision_uuid=rev,operation_uuid=op,schema_version=1,content_sha256='a'*64,source_clinic_uuid=clinic,entity_type='workers',entity_uuid=entity,operation='create',base_version=None,entity_version=1,changed_fields=['first_name'],payload={'employee_number':'ISSUER-1','first_name':'Test','last_name':'Issuer'},source_device_uuid=device,source_user_uuid=user,occurred_at=now))
 db.add(OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=op,event_uuid=event,content_sha256='a'*64,revision_uuid=rev,parent_revision_uuid=None,origin_user_uuid=user,origin_device_uuid=device,clinic_uuid=clinic,entity_type='workers',operation='create',policy_version='5A-P1-20261014',proof_transport_version=1,status='pending_proof',attempt_count=0,last_reason_code=str(dg),time_state='time_indeterminate',created_at=now,updated_at=now)); db.commit()
 req=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==op)); issuer=ProofIssuerService(MemoryKeyProvider({kid:priv}),key_id=kid); proof=issuer.issue(db,request_uuid=req.request_uuid); db.commit(); print('issued=1 signature_present=1 private_key_persisted=0')
 assert validate_required_fields(proof)=='valid' and verify_signature(proof,pub)=='valid'; assert verify_binding(proof,event_uuid=event,content_sha256='a'*64,clinic_uuid=clinic,entity_type='workers',entity_uuid=entity,operation='create',revision_uuid=rev,origin_user_uuid=user,origin_device_uuid=device,operation_uuid=op)=='valid'; key=db.get(ProofTrustedKey,kid); delegation=db.get(ProofDelegation,dg); assert verify_key_scope(proof,key,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=device)=='valid'; assert verify_delegation_scope(proof,delegation,clinic_uuid=clinic,origin_service_uuid=service,user_uuid=user,entity_type='workers',operation='create',policy_version='5A-P1-20261014')=='valid'; print('verification=signature_binding_key_scope_delegation_valid=1')
 from types import SimpleNamespace
 vr=SimpleNamespace(event_uuid=event,content_sha256='a'*64,evidence_refs={'clinic_uuid':str(clinic),'origin_service_uuid':str(service),'origin_device_uuid':str(device)},signature_result='valid',binding_result='valid',key_trust_result='active',delegation_result='valid',time_result='time_valid')
 assert evaluate_application_eligibility(event=SimpleNamespace(event_uuid=event,entity_uuid=entity),verification=vr,expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity,expected_content_sha256='a'*64).decision=='eligible'; print('eligibility=eligible_test_only=1 business_application=0')
 same=issuer.issue(db,request_uuid=req.request_uuid); assert same['signature']==proof['signature']; print('repeat_same_proof=1')
 altered=dict(proof); altered['content_sha256']='b'*64; assert verify_signature(altered,pub)=='invalid'; assert evaluate_application_eligibility(event=SimpleNamespace(event_uuid=event,entity_uuid=entity),verification=SimpleNamespace(**{**vars(vr),'content_sha256':'b'*64}),expected_clinic_uuid=clinic,expected_origin_service_uuid=service,expected_origin_device_uuid=device,expected_entity_uuid=entity,expected_content_sha256='a'*64).decision=='blocked'; print('content_or_signature_change=blocked_no_old_eligible_reuse=1')
 key.state='revoked'; assert verify_key_scope(proof,key,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=device)!='valid'; delegation.state='revoked'; assert verify_delegation_scope(proof,delegation,clinic_uuid=clinic,origin_service_uuid=service,user_uuid=user,entity_type='workers',operation='create',policy_version='5A-P1-20261014')!='valid'; print('revoked_key_or_delegation=blocked')
 delegation.state='active'; delegation.expires_at=now-timedelta(seconds=1); assert delegation.expires_at < now; print('expired_delegation=blocked_by_scope_time_boundary')
 row=db.scalar(select(OriginProof).where(OriginProof.request_uuid==req.request_uuid)); assert row is not None
 db.rollback()
with Session(eng) as db:
 assert db.scalar(select(func.count()).select_from(OriginProof))>=1; print('fresh_session=proof_persistent=1')
 # Request identity/content mismatch is rejected before any new proof row.
 with Session(eng) as db:
  req2=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==op)); req2.content_sha256='b'*64; db.flush(); before=db.scalar(select(func.count()).select_from(OriginProof))
  try: issuer.issue(db,request_uuid=req2.request_uuid)
  except ValueError as exc: assert str(exc)=='PROOF_REQUEST_EVENT_MISMATCH'
  else: raise AssertionError('content mismatch accepted')
  assert db.scalar(select(func.count()).select_from(OriginProof))==before; db.rollback(); print('request_identity_content_mismatch=rejected_no_extra_proof=1')
 # Key-provider failure and post-insert failure both roll back the caller transaction.
 with Session(eng) as db:
  event3=uuid.uuid4(); op3=uuid.uuid4(); rev3=uuid.uuid4(); db.add(SyncChange(change_uuid=event3,revision_uuid=rev3,operation_uuid=op3,schema_version=1,content_sha256='a'*64,source_clinic_uuid=clinic,entity_type='workers',entity_uuid=uuid.uuid4(),operation='create',base_version=None,entity_version=1,changed_fields=['first_name'],payload={'employee_number':'ISSUER-FAIL','first_name':'Test','last_name':'Fail'},source_device_uuid=device,source_user_uuid=user,occurred_at=now)); req3=OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=op3,event_uuid=event3,content_sha256='a'*64,revision_uuid=rev3,parent_revision_uuid=None,origin_user_uuid=user,origin_device_uuid=device,clinic_uuid=clinic,entity_type='workers',operation='create',policy_version='5A-P1-20261014',proof_transport_version=1,status='pending_proof',attempt_count=0,last_reason_code=str(dg),time_state='time_indeterminate',created_at=now,updated_at=now); db.add(req3); db.commit(); bad=ProofIssuerService(MemoryKeyProvider({}),key_id=kid)
  req3_uuid=req3.request_uuid
  try: bad.issue(db,request_uuid=req3_uuid)
  except ValueError as exc: assert str(exc)=='SIGNING_KEY_UNAVAILABLE'
  else: raise AssertionError('key failure accepted')
  db.rollback()
 with Session(eng) as db:
  req3=db.scalar(select(OriginProofRequest).where(OriginProofRequest.request_uuid==req3_uuid)); db.info['proof_issuer_fail_after_insert']=True
  try: issuer.issue(db,request_uuid=req3_uuid)
  except RuntimeError as exc: assert str(exc)=='INJECTED_PROOF_ISSUER_FAILURE_AFTER_INSERT'
  else: raise AssertionError('failure hook did not fire')
  db.rollback()
 with Session(eng) as db: assert db.scalar(select(OriginProof).where(OriginProof.request_uuid==req3_uuid)) is None and db.scalar(select(OriginProofRequest.status).where(OriginProofRequest.request_uuid==req3_uuid))=='pending_proof'; print('provider_or_save_failure=atomic_rollback=1')
 # Two independent transactions use the row lock and unique constraints; one proof survives.
 event4=uuid.uuid4(); op4=uuid.uuid4(); rev4=uuid.uuid4()
 req4=OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=op4,event_uuid=event4,content_sha256='a'*64,revision_uuid=rev4,parent_revision_uuid=None,origin_user_uuid=user,origin_device_uuid=device,clinic_uuid=clinic,entity_type='workers',operation='create',policy_version='5A-P1-20261014',proof_transport_version=1,status='pending_proof',attempt_count=0,last_reason_code=str(dg),time_state='time_indeterminate',created_at=now,updated_at=now)
 req4_uuid=req4.request_uuid
 with Session(eng) as db: db.add(SyncChange(change_uuid=event4,revision_uuid=rev4,operation_uuid=op4,schema_version=1,content_sha256='a'*64,source_clinic_uuid=clinic,entity_type='workers',entity_uuid=uuid.uuid4(),operation='create',base_version=None,entity_version=1,changed_fields=['first_name'],payload={'employee_number':'ISSUER-CONC','first_name':'Test','last_name':'Concurrent'},source_device_uuid=device,source_user_uuid=user,occurred_at=now)); db.add(req4); db.commit()
 outcomes=[]; lock=threading.Lock()
 def concurrent_issue():
  with Session(eng) as s:
   try:
    p=issuer.issue(s,request_uuid=req4_uuid); s.commit(); value=p['signature']
    with lock: outcomes.append(('ok',value))
   except Exception as exc:
    s.rollback(); raise
 ts=[threading.Thread(target=concurrent_issue) for _ in range(2)]
 [t.start() for t in ts]; [t.join() for t in ts]; assert len(outcomes)==2 and outcomes[0][1]==outcomes[1][1]
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(OriginProof).where(OriginProof.request_uuid==req4_uuid))==1
 print('concurrent_same_request=one_proof_one_binding_same_identity=1')
print('PASS isolated issuer verifier gate; no transport or application')
