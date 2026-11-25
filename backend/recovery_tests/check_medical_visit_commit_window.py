"""MedicalVisit inbox update commit-window regression."""
from __future__ import annotations
import os,sys,threading,uuid,base64
from datetime import datetime,timezone,timedelta
from pathlib import Path
from sqlalchemy import create_engine,select,func,update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session,sessionmaker
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.models.worker import Worker
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncEventInbox
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.proof_trust import ProofTrustedKey,ProofDelegation
from app.services.proof_verification_service import canonical_bytes,CANONICALIZATION_VERSION
from app.services.sync_journal import payload_sha256
from app.services.proof_revocation_service import register_and_revoke_delegation
from app.services.proof_verification_service import revocation_canonical_bytes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.services.sync_transport_worker import SyncTransportWorker

def main():
 u=make_url(os.environ.get('STAGE5_TARGET_DB') or '')
 if not u.database or u.database.lower()=='demo': raise RuntimeError('isolated target required')
 engine=create_engine(u.render_as_string(hide_password=False)); factory=sessionmaker(engine,expire_on_commit=False)
 event_id,visit_id,revision,source,generation,clinic=(uuid.uuid4() for _ in range(6)); now=datetime.now(timezone.utc)
 with Session(engine) as db:
  worker=db.scalar(select(Worker).order_by(Worker.id))
  if worker is None: raise RuntimeError('target worker fixture missing')
  worker_uuid=worker.uuid
  db.info.update(sync_apply_mode=True,stage3_write_contract=True)
  db.add(MedicalVisit(uuid=visit_id,worker_id=worker.id,worker_uuid=worker.uuid,visit_date='2026-01-01',site_name='before',status='draft',form_data={'case':'commit-window'},sync_status='pending_sync',version=1))
  parent_revision=uuid.uuid4();db.add(LocalRevision(revision_uuid=parent_revision,entity_type='medical_visits',entity_uuid=visit_id,local_version=1,kind='baseline',operation_uuid=None,created_at=now));db.commit()
 operation_uuid=uuid.uuid4();payload={'visit_date':'2026-01-01','site_name':'after','status':'draft','form_data':{'case':'commit-window','updated':True},'worker_uuid':str(worker_uuid),'operation_uuid':str(operation_uuid),'base_version':1}
 content_hash=payload_sha256(payload);service_uuid=uuid.uuid4();user_uuid=uuid.uuid4();key_id='medical-visit-inbox-'+event_id.hex[:8];private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes_raw();delegation_id=uuid.uuid4();proof_uuid=uuid.uuid4()
 proof={'event_uuid':str(event_id),'content_sha256':content_hash,'clinic_uuid':str(clinic),'entity_type':'medical_visits','entity_uuid':str(visit_id),'operation':'update','revision_uuid':str(revision),'parent_revision_uuid':str(parent_revision),'origin_user_uuid':str(user_uuid),'origin_device_uuid':str(source),'origin_service_uuid':str(service_uuid),'operation_uuid':str(operation_uuid),'authorization_policy_version':'5A-P1-20261014','authorization_reference':str(delegation_id),'proof_format_version':'1','signing_key_id':key_id,'issued_at':now.isoformat()};proof['signature']=base64.b64encode(private.sign(canonical_bytes(proof))).decode()
 with Session(engine) as db:
  db.add(ProofTrustedKey(key_id=key_id,clinic_uuid=clinic,origin_service_uuid=service_uuid,origin_device_uuid=source,registration_authority_uuid=service_uuid,public_key=base64.b64encode(public).decode(),algorithm='Ed25519',canonicalization_version=CANONICALIZATION_VERSION,state='active',registered_at=now));db.add(ProofDelegation(delegation_uuid=delegation_id,clinic_uuid=clinic,origin_service_uuid=service_uuid,user_uuid=user_uuid,entity_type='medical_visits',operation='update',policy_version='5A-P1-20261014',issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(days=1),state='active',authority_ref='fixture'));db.add(OriginProofTransportReceipt(receipt_uuid=uuid.uuid4(),proof_uuid=proof_uuid,event_uuid=event_id,content_sha256=content_hash,peer_device_uuid=source,source_device_uuid=source,source_generation_uuid=generation,channel='lease',proof=proof,status='acknowledged',received_at=now));db.commit()
 with Session(engine) as db:
  db.add(SyncEventInbox(event_uuid=event_id,source_clinic_uuid=clinic,source_device_uuid=source,source_generation_uuid=generation,source_sequence=1,entity_type='medical_visits',entity_uuid=visit_id,revision_uuid=revision,parent_revision_uuid=parent_revision,operation='update',schema_version=1,content_sha256=content_hash,payload=payload,status='received_waiting_application',received_at=now));db.commit()
 def make_revocation(reason):
  record={'revocation_uuid':str(uuid.uuid4()),'target_type':'delegation','target_ref':str(delegation_id),'reason_code':reason,'effective_at_declared':datetime.now(timezone.utc).isoformat(),'authority_key_id':key_id,'policy_version':'5A-P1-20261014','target_clinic_uuid':str(clinic),'target_origin_service_uuid':str(service_uuid),'canonicalization_version':'deterministic-json-restricted-v1','authority_ref':'fixture-authority'}
  record['signature']=base64.b64encode(private.sign(revocation_canonical_bytes(record))).decode(); return record
 if os.environ.get('LOCK_CASE') in {'revocation_first','application_first'}:
  case=os.environ['LOCK_CASE']; lock_ready=threading.Event(); release=threading.Event(); app_started=threading.Event(); revoke_started=threading.Event(); results=[]
  def revoke_worker(hold=False):
   with Session(engine) as revoke_db:
    revoke_started.set() if not hold else None
    delegation=revoke_db.scalar(select(ProofDelegation).where(ProofDelegation.delegation_uuid==delegation_id).with_for_update()); lock_ready.set() if hold else None
    register_and_revoke_delegation(revoke_db,make_revocation('concurrent-'+case),clinic_uuid=clinic,policy_version='5A-P1-20261014')
    if hold: release.wait(10)
    revoke_db.commit()
  if case=='revocation_first':
   rt=threading.Thread(target=revoke_worker,args=(True,));rt.start();assert lock_ready.wait(10)
   def app_run():
    w=SyncTransportWorker(factory,peer_device_uuid=source,channel='lease',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None);results.append(w.run_application_once(limit=1,event_uuid=event_id))
   at=threading.Thread(target=app_run);at.start();import time;time.sleep(.3);assert at.is_alive();release.set();rt.join(10);at.join(10)
   with Session(engine) as db:
    inbox=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_id));assert inbox.application_error_code=='DELEGATION_REVOKED' and inbox.application_error_message=='DELEGATION_REVOKED' and inbox.status=='blocked_authorization' and visit.site_name=='before';print('revocation_first=lock_waited=1 reason=DELEGATION_REVOKED inbox_status=blocked_authorization visit_unchanged=1 inbox_applied=0')
  else:
   def pause_before(row): app_started.set();release.wait(10)
   def app_run():
    w=SyncTransportWorker(factory,peer_device_uuid=source,channel='lease',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None,before_medical_visit_business_apply=pause_before);results.append(w.run_application_once(limit=1,event_uuid=event_id))
   at=threading.Thread(target=app_run);at.start();assert app_started.wait(10)
   rt=threading.Thread(target=revoke_worker);rt.start();assert revoke_started.wait(10);import time;time.sleep(.3);assert rt.is_alive();release.set();at.join(10);rt.join(10)
   with Session(engine) as db:
    inbox=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_id));revs=db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==visit_id));assert inbox.status=='applied' and visit.site_name=='after' and revs==2;print('application_first=revocation_waited=1 business_commit_before_revoke=1 inbox_applied=1 revisions=2')
  engine.dispose();return
 if os.environ.get('REVOKE_BEFORE_APPLY')=='1':
  record={'revocation_uuid':str(uuid.uuid4()),'target_type':'delegation','target_ref':str(delegation_id),'reason_code':'fixture-revoked-before-apply','effective_at_declared':now.isoformat(),'authority_key_id':key_id,'policy_version':'5A-P1-20261014','target_clinic_uuid':str(clinic),'target_origin_service_uuid':str(service_uuid),'canonicalization_version':'deterministic-json-restricted-v1','authority_ref':'fixture-authority'}
  record['signature']=base64.b64encode(private.sign(revocation_canonical_bytes(record))).decode()
  with Session(engine) as db:
   register_and_revoke_delegation(db,record,clinic_uuid=clinic,policy_version='5A-P1-20261014');db.commit()
  with Session(engine) as db:
   print('business_delegation_revoked=1 state=',db.scalar(select(ProofDelegation.state).where(ProofDelegation.delegation_uuid==delegation_id)))
  w=SyncTransportWorker(factory,peer_device_uuid=source,channel='lease',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None)
  assert w.run_application_once(limit=1,event_uuid=event_id)==0
  with Session(engine) as db:
   inbox=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_id));assert inbox.status=='received_waiting_application' and inbox.application_error_message=='DELEGATION_REVOKED' and visit.site_name=='before';print('revoked_before_first_write=1 reason=DELEGATION_REVOKED visit_unchanged=1 inbox_applied=0')
  engine.dispose();return
 claimed=threading.Event();release=threading.Event();errors=[];revoked_after=False
 def pause(row):
  nonlocal revoked_after
  claimed.set()
  if os.environ.get('REVOKE_AFTER_COMMIT')=='1' and not revoked_after:
   record={'revocation_uuid':str(uuid.uuid4()),'target_type':'delegation','target_ref':str(delegation_id),'reason_code':'fixture-revoked-after-commit','effective_at_declared':datetime.now(timezone.utc).isoformat(),'authority_key_id':key_id,'policy_version':'5A-P1-20261014','target_clinic_uuid':str(clinic),'target_origin_service_uuid':str(service_uuid),'canonicalization_version':'deterministic-json-restricted-v1','authority_ref':'fixture-authority'};record['signature']=base64.b64encode(private.sign(revocation_canonical_bytes(record))).decode()
   with Session(engine) as revoke_db: register_and_revoke_delegation(revoke_db,record,clinic_uuid=clinic,policy_version='5A-P1-20261014');revoke_db.commit()
   revoked_after=True;print('business_delegation_revoked_after_commit=1')
  release.wait(10)
 def run_a():
  try:
   w=SyncTransportWorker(factory,peer_device_uuid=source,channel='lease',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None,after_application_business_commit=pause)
   w.run_application_once(limit=1,event_uuid=event_id)
  except Exception as e: errors.append(repr(e));claimed.set()
 ta=threading.Thread(target=run_a);ta.start();assert claimed.wait(10),errors
 with Session(engine) as db:
  row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_id));assert row.status=='applying' and visit.site_name=='after';print('after_business_commit=visible inbox=applying visit=updated')
 w_b=SyncTransportWorker(factory,peer_device_uuid=source,channel='lease',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None)
 assert w_b.run_application_once(limit=1,event_uuid=event_id)==0;print('live_lease_takeover=blocked')
 with Session(engine) as db:db.execute(update(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id).values(application_lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)));db.commit()
 assert w_b.run_application_once(limit=1,event_uuid=event_id)==1;print('expired_lease_recovered=1')
 release.set();ta.join(10);assert not ta.is_alive()
 with Session(engine) as db:
  row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));visit=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==visit_id));revs=db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==visit_id));assert row.status=='applied' and visit.site_name=='after' and revs==2;print('final inbox=applied visit=updated revisions=2 stale_owner_cannot_overwrite=1')
 engine.dispose()
if __name__=='__main__':main()
