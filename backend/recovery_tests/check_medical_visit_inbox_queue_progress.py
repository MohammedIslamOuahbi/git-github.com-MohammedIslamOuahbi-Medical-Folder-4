"""Queue progress: authorization-blocked rows do not starve later work."""
from __future__ import annotations
import os,sys,uuid,base64
from datetime import datetime,timezone,timedelta
from pathlib import Path
from sqlalchemy import create_engine,select,func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session,sessionmaker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.models.worker import Worker
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncEventInbox
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.proof_trust import ProofTrustedKey,ProofDelegation
from app.services.proof_verification_service import canonical_bytes,CANONICALIZATION_VERSION
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_worker import SyncTransportWorker

def main():
 u=make_url(os.environ.get('STAGE5_TARGET_DB') or '')
 if not u.database or u.database.lower()=='demo':raise RuntimeError('isolated target required')
 engine=create_engine(u.render_as_string(hide_password=False));factory=sessionmaker(engine,expire_on_commit=False);now=datetime.now(timezone.utc)
 ids=[uuid.uuid4() for _ in range(3)]; visits=[uuid.uuid4() for _ in range(3)]; revisions=[uuid.uuid4() for _ in range(3)]; source,generation,clinic=(uuid.uuid4() for _ in range(3))
 proofs=[]
 with Session(engine) as db:
  worker=db.scalar(select(Worker).order_by(Worker.id));
  if worker is None:raise RuntimeError('target worker fixture missing')
  for i,(event_id,visit_id,rev) in enumerate(zip(ids,visits,revisions)):
   db.info.update(sync_apply_mode=True,stage3_write_contract=True);db.add(MedicalVisit(uuid=visit_id,worker_id=worker.id,worker_uuid=worker.uuid,visit_date='2026-01-01',site_name='before-'+str(i),status='draft',form_data={'queue':i},sync_status='pending_sync',version=1));db.add(LocalRevision(revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=visit_id,local_version=1,kind='baseline',operation_uuid=None,created_at=now))
   op=uuid.uuid4();parent=db.scalar(select(LocalRevision.revision_uuid).where(LocalRevision.entity_uuid==visit_id));payload={'visit_date':'2026-01-01','site_name':'after-'+str(i),'status':'draft','form_data':{'queue':i,'updated':True},'worker_uuid':str(worker.uuid),'operation_uuid':str(op),'base_version':1};content=payload_sha256(payload);service=uuid.uuid4();user=uuid.uuid4();kid='queue-'+event_id.hex[:8];priv=Ed25519PrivateKey.generate();deleg=uuid.uuid4();proof={'event_uuid':str(event_id),'content_sha256':content,'clinic_uuid':str(clinic),'entity_type':'medical_visits','entity_uuid':str(visit_id),'operation':'update','revision_uuid':str(rev),'parent_revision_uuid':str(parent),'origin_user_uuid':str(user),'origin_device_uuid':str(source),'origin_service_uuid':str(service),'operation_uuid':str(op),'authorization_policy_version':'5A-P1-20261014','authorization_reference':str(deleg),'proof_format_version':'1','signing_key_id':kid,'issued_at':now.isoformat()};proof['signature']=base64.b64encode(priv.sign(canonical_bytes(proof))).decode();state='revoked' if i==0 else 'active';db.add(ProofTrustedKey(key_id=kid,clinic_uuid=clinic,origin_service_uuid=service,origin_device_uuid=source,registration_authority_uuid=service,public_key=base64.b64encode(priv.public_key().public_bytes_raw()).decode(),algorithm='Ed25519',canonicalization_version=CANONICALIZATION_VERSION,state='active',registered_at=now));db.add(ProofDelegation(delegation_uuid=deleg,clinic_uuid=clinic,origin_service_uuid=service,user_uuid=user,entity_type='medical_visits',operation='update',policy_version='5A-P1-20261014',issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(days=1),state=state,authority_ref='queue-fixture'));db.add(SyncEventInbox(event_uuid=event_id,source_clinic_uuid=clinic,source_device_uuid=source,source_generation_uuid=generation,source_sequence=i+1,entity_type='medical_visits',entity_uuid=visit_id,revision_uuid=rev,parent_revision_uuid=parent,operation='update',schema_version=1,content_sha256=content,payload=payload,status='received_waiting_application',received_at=now+timedelta(seconds=i)));proofs.append((event_id,content,proof,kid,deleg,priv,service,visit_id))
  db.commit()
  for i,(event_id,content,proof,kid,deleg,priv,service,visit_id) in enumerate(proofs):
   if i!=1:db.add(OriginProofTransportReceipt(receipt_uuid=uuid.uuid4(),proof_uuid=uuid.uuid4(),event_uuid=event_id,content_sha256=content,peer_device_uuid=source,source_device_uuid=source,source_generation_uuid=generation,channel='queue',proof=proof,status='acknowledged',received_at=now))
  db.commit()
 w=SyncTransportWorker(factory,peer_device_uuid=source,channel='queue',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None)
 for expected in (ids[0],ids[1],ids[2]):
  result=w.run_application_once(limit=1,event_uuid=expected);print('poll_claim=',expected,'result=',result)
 with Session(engine) as db:
  rows={r.event_uuid:r for r in db.scalars(select(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids))).all()};assert rows[ids[0]].status=='blocked_authorization' and rows[ids[0]].application_error_code=='DELEGATION_REVOKED';assert rows[ids[1]].status=='blocked_authorization' and rows[ids[1]].application_error_code=='BUSINESS_AUTHORIZATION_EVIDENCE_MISSING';assert rows[ids[2]].status=='applied';assert db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid==visits[2]))==1;print('revoked=blocked missing_evidence=blocked later_valid=applied attempts=',[(str(i),rows[i].application_attempt_count) for i in ids])
 # Restore exact missing receipt; it becomes eligible once, then survives worker restart.
 event_id,content,proof,kid,deleg,priv,service,visit_id=proofs[1]
 with Session(engine) as db:db.add(OriginProofTransportReceipt(receipt_uuid=uuid.uuid4(),proof_uuid=uuid.uuid4(),event_uuid=event_id,content_sha256=content,peer_device_uuid=source,source_device_uuid=source,source_generation_uuid=generation,channel='queue',proof=proof,status='acknowledged',received_at=now));db.commit()
 assert w.run_application_once(limit=1,event_uuid=event_id)==1
 w2=SyncTransportWorker(factory,peer_device_uuid=source,channel='queue',publisher_device_uuid=source,publisher_generation_uuid=generation,publisher_clinic_uuid=clinic,sender=lambda _:None);assert w2.run_application_once(limit=1,event_uuid=event_id)==0
 with Session(engine) as db:row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id));assert row.status=='applied';print('evidence_restored=applied restart_no_duplicate=1')
 engine.dispose()
if __name__=='__main__':main()
