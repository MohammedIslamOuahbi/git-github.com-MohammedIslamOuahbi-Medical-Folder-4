"""Isolated OriginProof transport fixture/runner (no business application)."""
import os, sys, uuid, time, socket, subprocess, base64
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncRelayAuthorization
from app.models.origin_proof import OriginProof
from app.models.origin_proof_delivery import OriginProofDelivery
from app.services.central_sync_service import CentralSyncService

root=Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class OriginProofFixture:
 source: str
 target: str
 src_dev: uuid.UUID
 dst_dev: uuid.UUID
 gen: uuid.UUID
 clinic: uuid.UUID
 channel: str
 src_secret: str
 dst_secret: str
 event: uuid.UUID
 proof_uuid: uuid.UUID
 entity: uuid.UUID
 revision: uuid.UUID
 operation: uuid.UUID

def prepare_origin_proof_fixture(source: str, target: str, *, include_target_event: bool = True) -> OriginProofFixture:
 """Prepare only durable source/target proof data; never starts processes."""
 from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
 from app.models.sync_change import SyncChange
 from app.models.proof_pending import OriginProofRequest
 from app.models.proof_trust import ProofTrustedKey, ProofDelegation
 from app.models.sync_transport import SyncTransportEvent
 from app.services.proof_issuer_service import ProofIssuerService, MemoryKeyProvider
 from app.services.sync_journal import payload_sha256
 from datetime import timedelta
 src_dev,dst_dev=uuid.uuid4(),uuid.uuid4(); gen=uuid.uuid4(); clinic=uuid.uuid4()
 channel='proof-'+uuid.uuid4().hex[:8]; src_secret=uuid.uuid4().hex; dst_secret=uuid.uuid4().hex
 now=datetime.now(timezone.utc)
 content_hash=payload_sha256({'employee_number':'HTTP-PROOF','first_name':'Proof','last_name':'Transfer'})
 for url,dev,secret in ((source,src_dev,src_secret),(target,dst_dev,dst_secret)):
  with Session(create_engine(url)) as db:
   db.add(SyncDevice(uuid=dev,installation_uuid=uuid.uuid4(),device_code='proof-'+dev.hex,device_name='proof-test',registered_at=now,central_secret_hash=CentralSyncService()._hash_secret(secret),is_active=True)); db.commit()
 with Session(create_engine(source)) as db:
  if db.scalar(select(SyncDevice).where(SyncDevice.uuid==dst_dev)) is None:
   db.add(SyncDevice(uuid=dst_dev,installation_uuid=uuid.uuid4(),device_code='peer-'+dst_dev.hex,device_name='peer',registered_at=now,central_secret_hash=CentralSyncService()._hash_secret(dst_secret))); db.commit()
 with Session(create_engine(target)) as db:
  if db.scalar(select(SyncDevice).where(SyncDevice.uuid==src_dev)) is None:
   db.add(SyncDevice(uuid=src_dev,installation_uuid=uuid.uuid4(),device_code='peer-'+src_dev.hex,device_name='peer',registered_at=now,central_secret_hash=CentralSyncService()._hash_secret(src_secret))); db.commit()
 with Session(create_engine(source)) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=src_dev,origin_device_uuid=src_dev,origin_generation_uuid=gen,destination_device_uuid=dst_dev,channel=channel,created_at=now,is_active=True)); db.commit()
 with Session(create_engine(target)) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=dst_dev,origin_device_uuid=src_dev,origin_generation_uuid=gen,destination_device_uuid=dst_dev,channel=channel,created_at=now,is_active=True)); db.commit()
 key=Ed25519PrivateKey.generate(); kid='http-proof-'+uuid.uuid4().hex[:8]; user=uuid.uuid4(); entity=uuid.uuid4(); rev=uuid.uuid4(); op=uuid.uuid4(); event=uuid.uuid4(); delegation=uuid.uuid4()
 with Session(create_engine(source)) as db:
  db.add(ProofTrustedKey(key_id=kid,clinic_uuid=clinic,origin_service_uuid=src_dev,origin_device_uuid=src_dev,registration_authority_uuid=uuid.uuid4(),public_key=base64.b64encode(key.public_key().public_bytes_raw()).decode(),algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now))
  db.add(ProofDelegation(delegation_uuid=delegation,clinic_uuid=clinic,origin_service_uuid=src_dev,user_uuid=user,entity_type='workers',operation='create',policy_version='5A-P1-20261014',issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(days=7),state='active',authority_ref='fixture'))
  db.add(SyncChange(change_uuid=event,revision_uuid=rev,operation_uuid=op,schema_version=1,content_sha256=content_hash,source_clinic_uuid=clinic,entity_type='workers',entity_uuid=entity,operation='create',entity_version=1,payload={'employee_number':'HTTP-PROOF','first_name':'Proof','last_name':'Transfer'},source_device_uuid=src_dev,source_user_uuid=user,occurred_at=now))
  req=OriginProofRequest(request_uuid=uuid.uuid4(),operation_uuid=op,event_uuid=event,content_sha256=content_hash,revision_uuid=rev,origin_user_uuid=user,origin_device_uuid=src_dev,clinic_uuid=clinic,entity_type='workers',operation='create',policy_version='5A-P1-20261014',proof_transport_version=1,status='pending_proof',attempt_count=0,last_reason_code=str(delegation),time_state='time_indeterminate',created_at=now,updated_at=now); db.add(req); db.commit(); ProofIssuerService(MemoryKeyProvider({kid:key}),key_id=kid).issue(db,request_uuid=req.request_uuid); db.commit(); proof=db.scalar(select(OriginProof).where(OriginProof.event_uuid==event)); proof_uuid=proof.proof_uuid; db.add(OriginProofDelivery(proof_uuid=proof_uuid,peer_device_uuid=dst_dev,channel=channel,status='pending',attempt_count=0,created_at=now)); db.commit()
 if include_target_event:
  with Session(create_engine(target)) as db:
   db.add(SyncTransportEvent(event_uuid=event,source_clinic_uuid=clinic,source_device_uuid=src_dev,source_generation_uuid=gen,source_sequence=1,entity_type='workers',entity_uuid=entity,revision_uuid=rev,operation='create',schema_version=1,content_sha256='a'*64,payload={'employee_number':'HTTP-PROOF','first_name':'Proof','last_name':'Transfer'},origin_kind='remote',created_at=now)); db.commit()
 with Session(create_engine(target)) as db:
  db.add(ProofTrustedKey(key_id=kid,clinic_uuid=clinic,origin_service_uuid=src_dev,origin_device_uuid=src_dev,registration_authority_uuid=uuid.uuid4(),public_key=base64.b64encode(key.public_key().public_bytes_raw()).decode(),algorithm='Ed25519',canonicalization_version='deterministic-json-restricted-v1',state='active',registered_at=now))
  db.add(ProofDelegation(delegation_uuid=delegation,clinic_uuid=clinic,origin_service_uuid=src_dev,user_uuid=user,entity_type='workers',operation='create',policy_version='5A-P1-20261014',issued_at=now-timedelta(minutes=1),expires_at=now+timedelta(days=7),state='active',authority_ref='fixture')); db.commit()
 return OriginProofFixture(source,target,src_dev,dst_dev,gen,clinic,channel,src_secret,dst_secret,event,proof_uuid,entity,rev,op)

def port():
 s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
def head(url):
 e=create_engine(url)
 with e.connect() as c:
  name,=c.execute(text('select current_database()')).one(); ver=c.execute(text('select version_num from alembic_version')).scalar()
  assert str(ver)=='20261008_27', (name,ver)
  return name
def start(url,p,extra_env=None):
 env={**os.environ,'DATABASE_URL':url,'PROOF_TRANSPORT_ENABLED':'1',**(extra_env or {})}
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def main():
 source=os.environ.get("STAGE5_SOURCE_DB"); target=os.environ.get("STAGE5_TARGET_DB"); procs=[]
 if not source or not target: raise SystemExit("STAGE5_SOURCE_DB and STAGE5_TARGET_DB are required")
 if any(x and ("demo" in x.lower() or "clinic" in x.lower()) for x in (source,target)): raise SystemExit("refusing demo/clinic database")
 try:
  print('source_database=',head(source),'target_database=',head(target),'head=20261008_27')
  fixture = prepare_origin_proof_fixture(source, target)
  src_dev, dst_dev, gen, clinic = fixture.src_dev, fixture.dst_dev, fixture.gen, fixture.clinic
  channel, src_secret, dst_secret = fixture.channel, fixture.src_secret, fixture.dst_secret
  event, proof_uuid = fixture.event, fixture.proof_uuid
  print('fixture_devices_and_relay=prepared')
  print('issued_proof_and_delivery=1')
  print('destination_event_fixture=1')
  ps,pt=port(),port(); procs=[start(source,ps),start(target,pt)]
  deadline=time.time()+20
  import requests
  while time.time()<deadline and all(p.poll() is None for p in procs):
   try:
    if requests.get(f'http://127.0.0.1:{ps}/openapi.json',timeout=1).status_code==200 and requests.get(f'http://127.0.0.1:{pt}/openapi.json',timeout=1).status_code==200: break
   except requests.RequestException: pass
   time.sleep(.2)
  else: raise RuntimeError('API_READY_TIMEOUT')
  print('api_pids=',procs[0].pid,procs[1].pid,'ports=',ps,pt)
  import tempfile
  pause=str(Path(tempfile.gettempdir())/('proof-pause-'+uuid.uuid4().hex)); release=str(Path(tempfile.gettempdir())/('proof-release-'+uuid.uuid4().hex))
  wenv={**os.environ,'DATABASE_URL':source,'PROOF_DELIVERY_LEASE_SECONDS':'2','WORKER_PEER':str(dst_dev),'WORKER_CHANNEL':channel,'WORKER_TARGET':f'http://127.0.0.1:{pt}','WORKER_SOURCE':f'http://127.0.0.1:{ps}','WORKER_SECRET':dst_secret,'WORKER_ORIGIN_DEVICE':str(src_dev),'WORKER_ORIGIN_GENERATION':str(gen),'WORKER_CAPABILITY_TARGET':f'http://127.0.0.1:{pt}','WORKER_CONNECTION_SCOPE':channel,'WORKER_CAPABILITY_VERSIONS':'[1]','WORKER_PUBLISHER_DEVICE':str(src_dev),'WORKER_PUBLISHER_GENERATION':str(gen),'WORKER_PUBLISHER_CLINIC':str(clinic),'PROOF_TRANSPORT_ENABLED':'1','WORKER_CYCLES':'1','WORKER_LEASE_SECONDS':'2','PROOF_AFTER_RECEIVE_PAUSE_FILE':pause,'PROOF_AFTER_RECEIVE_RELEASE_FILE':release}
  worker1=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=root,env=wenv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True); procs.append(worker1)
  deadline=time.time()+20
  while time.time()<deadline and not Path(pause).exists(): time.sleep(.05)
  if not Path(pause).exists(): raise RuntimeError('PROOF_RECEIVE_PAUSE_TIMEOUT')
  with Session(create_engine(source)) as db: assert db.scalar(select(OriginProofDelivery.status).order_by(OriginProofDelivery.id.desc()))!='delivered'
  from app.models.origin_proof_transport import OriginProofTransportReceipt
  with Session(create_engine(target)) as db: receipt_before=db.scalar(select(OriginProofTransportReceipt.receipt_uuid).where(OriginProofTransportReceipt.event_uuid==event))
  with Session(create_engine(source)) as db:
   old_row=db.scalar(select(OriginProofDelivery).where(OriginProofDelivery.proof_uuid==proof_uuid,OriginProofDelivery.peer_device_uuid==dst_dev,OriginProofDelivery.channel==channel)); old_delivery_id=old_row.id; old_token=old_row.lease_token
  worker1.terminate(); worker1.wait(timeout=10); print('worker1_pid=',worker1.pid,'interrupted_after_receive=1')
  time.sleep(3); wenv.pop('PROOF_AFTER_RECEIVE_PAUSE_FILE',None); wenv.pop('PROOF_AFTER_RECEIVE_RELEASE_FILE',None)
  pause2=str(Path(tempfile.gettempdir())/('proof-claim-pause-'+uuid.uuid4().hex)); release2=str(Path(tempfile.gettempdir())/('proof-claim-release-'+uuid.uuid4().hex)); wenv.update({'PROOF_AFTER_CLAIM_PAUSE_FILE':pause2,'PROOF_AFTER_CLAIM_RELEASE_FILE':release2,'PROOF_CLAIM_HOOK_TIMEOUT':'20','PROOF_DELIVERY_LEASE_SECONDS':'20'})
  worker2=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=root,env=wenv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True); procs.append(worker2); deadline=time.time()+20
  while time.time()<deadline and not Path(pause2).exists(): time.sleep(.05)
  if not Path(pause2).exists(): raise RuntimeError('WORKER2_AFTER_CLAIM_TIMEOUT')
  from app.services.sync_transport_service import SyncTransportService
  with Session(create_engine(source)) as db:
   current=db.scalar(select(OriginProofDelivery).where(OriginProofDelivery.proof_uuid==proof_uuid,OriginProofDelivery.peer_device_uuid==dst_dev,OriginProofDelivery.channel==channel)); assert current.lease_token!=old_token and current.status=='leased'
   try: SyncTransportService().acknowledge_proof_delivery(db,delivery_id=old_delivery_id,peer_device_uuid=dst_dev,channel=channel,lease_token=old_token)
   except Exception as exc: print('stale_ack_rejected=',type(exc).__name__); db.rollback()
   else: raise AssertionError('stale lease accepted')
  worker2_release=Path(release2); worker2_release.write_text('release',encoding='utf-8'); out,_=worker2.communicate(timeout=30); print('worker2_pid=',worker2.pid); print(out)
  if worker2.returncode!=0: raise RuntimeError(f'WORKER2_FAILED_{worker2.returncode}')
  from app.models.proof_trust import ProofTrustedKey
  with Session(create_engine(source)) as db:
   d=db.scalar(select(OriginProofDelivery).order_by(OriginProofDelivery.id.desc())); print('source_delivery=',d.status,'attempts=',d.attempt_count)
  with Session(create_engine(target)) as db:
   rs=db.scalars(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==event)).all(); assert len(rs)==1 and rs[0].status=='acknowledged' and rs[0].receipt_uuid==receipt_before; print('target_receipts_for_event=',len(rs),'receipt_status=',rs[0].status,'receipt_uuid_stable=1')
   from app.services.proof_verification_service import verify_signature
   assert verify_signature(rs[0].proof, db.scalar(select(ProofTrustedKey.public_key).where(ProofTrustedKey.key_id==rs[0].proof['signing_key_id'])))=='valid'; print('target_verifier_signature=valid business_application=0')
 finally:
  for p in procs:
   if p.poll() is None: p.terminate(); p.wait(timeout=10)
 
 

if __name__ == "__main__":
 main()

