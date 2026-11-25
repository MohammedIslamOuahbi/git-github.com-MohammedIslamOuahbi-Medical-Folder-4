import os,sys,time,uuid,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncTransportEvent,SyncEventDelivery,SyncPublicationReceipt,SyncRelayAuthorization,SyncTransportCursor
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
B=make_url(settings.database_url)
SOURCE_DB=os.environ.get('STAGE5_TRANSPORT_SOURCE_DB')
DEST_DB=os.environ.get('STAGE5_TRANSPORT_DEST_DB')
if not SOURCE_DB or not DEST_DB:
 raise RuntimeError('STAGE5_TRANSPORT_SOURCE_DB and STAGE5_TRANSPORT_DEST_DB are required')
A=B.set(database=SOURCE_DB).render_as_string(hide_password=False); D=B.set(database=DEST_DB).render_as_string(hide_password=False)
SRC,PEER,GEN,CLINIC,EID=[uuid.uuid4() for _ in range(5)]; VISIT_ID=uuid.uuid4(); CH='rx-'+SRC.hex[:8]; SECRET='stage4-receive-revoke'; root=Path(tempfile.gettempdir()); release=root/f'rx-release-{CH}'; status=root/f'rx-status-{CH}'; procs=[]
def stop(p):
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(5)
  except: p.kill()
def api(url,port):
 e=os.environ.copy(); e['DATABASE_URL']=url
 log=Path(tempfile.gettempdir())/f'rx-api-{CH}-{port}.log'
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=log.open('w'),stderr=subprocess.STDOUT)
def wait_port(port):
 import socket
 end=time.time()+30
 while time.time()<end:
  try:
   with socket.create_connection(('127.0.0.1',port),.3): return
  except OSError: time.sleep(.2)
 raise RuntimeError(f'API port {port} not ready')
try:
 for f in (release,status): f.unlink(missing_ok=True)
 h=CentralSyncService()._hash_secret(SECRET)
 with Session(create_engine(A)) as db:
  for x in (SRC,PEER): db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='rx-'+x.hex,device_name='rx',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True))
  payload={'synthetic_receive_revoke':EID.hex}; db.add(SyncChange(change_uuid=EID,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=VISIT_ID,operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=SRC,source_generation_uuid=GEN,source_sequence=1700,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit()
 with Session(create_engine(D)) as db:
  baseline_visit_count=db.scalar(select(func.count()).select_from(MedicalVisit))
  for x in (SRC,PEER):
   if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==x)):
    db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='rx-'+x.hex,device_name='rx',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True))
  db.commit()
 with Session(create_engine(A)) as db:
  svc=SyncTransportService(); svc.publish_committed(db,channel=CH,limit=10,source_device_uuid=SRC,source_generation_uuid=GEN,source_clinic_uuid=CLINIC); svc.queue_for_peer(db,peer_device_uuid=PEER,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=SRC,limit=10); db.commit()
 p1=api(A,8911); p2=api(D,8912); procs += [p1,p2]; wait_port(8911); wait_port(8912)
 env={**os.environ,'DATABASE_URL':A,'WORKER_PEER':str(PEER),'WORKER_CHANNEL':CH,'WORKER_PUBLISHER_DEVICE':str(SRC),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC),'WORKER_CARRIER':str(PEER),'WORKER_TARGET':'http://127.0.0.1:8912','WORKER_SOURCE':'http://127.0.0.1:8911','WORKER_SECRET':SECRET,'WORKER_LEASE_SECONDS':'30','WORKER_ID':'rx','WORKER_STATUS_FILE':str(status),'WORKER_AFTER_RECEIVE_RELEASE_FILE':str(release)}
 w=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); procs.append(w)
 end=time.time()+30
 while time.time()<end and (not status.exists() or 'before_ack_waiting' not in status.read_text()): time.sleep(.1)
 if not status.exists() or 'before_ack_waiting' not in status.read_text():
  print('diagnostic timeout worker_pid=',w.pid,'worker_exit=',w.poll(),'status=',status.read_text() if status.exists() else 'missing')
  print('diagnostic worker_stderr=',w.stderr.read() if w.poll() is not None else 'running')
  for port in (8911,8912):
   log=Path(tempfile.gettempdir())/f'rx-api-{CH}-{port}.log'; print('diagnostic api_port=',port,'tail=',log.read_text()[-3000:] if log.exists() else 'missing')
  raise AssertionError('no receive-before-ack stop; see diagnostic phase output')
 with Session(create_engine(D)) as db:
  assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))==1 and db.scalar(select(func.count()).select_from(SyncTransportEvent).where(SyncTransportEvent.event_uuid==EID))==1 and db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==EID,SyncPublicationReceipt.channel==CH))==1
 print('diagnostic receive_commit inbox=1 source=1 receipt=1')
 with Session(create_engine(A)) as db:
  scopes=db.scalars(select(SyncRelayAuthorization).where(SyncRelayAuthorization.carrier_device_uuid==PEER,SyncRelayAuthorization.origin_device_uuid==SRC,SyncRelayAuthorization.origin_generation_uuid==GEN,SyncRelayAuthorization.destination_device_uuid==PEER,SyncRelayAuthorization.channel==CH)).all(); assert scopes
  for s in scopes: s.is_active=False
  db.commit()
 release.touch(); assert w.wait(30)==0; print('worker_trace',w.stderr.read()[-1500:])
 with Session(create_engine(A)) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.channel==CH)); print('diagnostic after_revoke status=',d.status,'error=',d.last_error_code); assert d.status=='rejected' and d.last_error_code=='RELAY_AUTHORIZATION_REVOKED'
 with Session(create_engine(D)) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))==1
 with Session(create_engine(A)) as db:
  for s in db.scalars(select(SyncRelayAuthorization).where(SyncRelayAuthorization.carrier_device_uuid==PEER,SyncRelayAuthorization.origin_device_uuid==SRC,SyncRelayAuthorization.origin_generation_uuid==GEN,SyncRelayAuthorization.destination_device_uuid==PEER,SyncRelayAuthorization.channel==CH)).all(): s.is_active=True
  db.commit()
 with Session(create_engine(A)) as db: SyncTransportService().resume_relay_delivery(db,event_uuid=EID,peer_device_uuid=PEER,channel=CH,publisher_device_uuid=SRC,publisher_generation_uuid=GEN,publisher_clinic_uuid=CLINIC)
 w2=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env={**env,'WORKER_ID':'rx-resume','WORKER_AFTER_RECEIVE_RELEASE_FILE':''},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); procs.append(w2); assert w2.wait(30)==0; print('resume_worker_trace',w2.stderr.read()[-1000:])
 with Session(create_engine(A)) as db:
  delivery=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.channel==CH))
  assert delivery and delivery.status=='delivered' and delivery.peer_device_uuid==PEER and delivery.publisher_device_uuid==SRC and delivery.publisher_generation_uuid==GEN and delivery.clinic_uuid==CLINIC
 with Session(create_engine(D)) as db:
  inbox=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==EID)); receipt=db.scalar(select(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==EID,SyncPublicationReceipt.channel==CH)); cursor=db.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==PEER,SyncTransportCursor.source_device_uuid==SRC,SyncTransportCursor.source_generation_uuid==GEN,SyncTransportCursor.channel==CH,SyncTransportCursor.publisher_device_uuid==SRC,SyncTransportCursor.publisher_generation_uuid==GEN,SyncTransportCursor.clinic_uuid==CLINIC))
  assert inbox and receipt and receipt.publisher_device_uuid==SRC and receipt.publisher_generation_uuid==GEN and receipt.clinic_uuid==CLINIC
  assert cursor and cursor.last_publication_event_uuid==EID and cursor.last_publish_sequence==receipt.publish_sequence
  assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))==1 and db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==EID,SyncPublicationReceipt.channel==CH))==1 and db.scalar(select(func.count()).select_from(MedicalVisit))==baseline_visit_count and db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid==VISIT_ID))==0
  print('durable_new_session delivery=delivered inbox=1 receipt=1 cursor_event=match cursor_publish_sequence=',cursor.last_publish_sequence,'scope=publisher/origin/generation/clinic match')
 with Session(create_engine(D)) as db:
  outcome=SyncTransportService().apply_inbox_once(db, limit=1, event_uuid=EID)
  inbox=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))
  assert outcome['failed']==1 and inbox.status=='received_waiting_application' and inbox.application_error_code in {'ValueError','INBOX_ENTITY_OPERATION_UNSUPPORTED'}
  assert db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid==VISIT_ID))==0
  print('post_revoke_consumer=deferred business_applied=0 reason=',inbox.application_error_message)
 print('PASS receive commit -> revoke -> ACK rejected -> regrant -> resume -> delivered; inbox=1 receipt=1 cursor=1')
finally:
 for p in reversed(procs): stop(p)
 for f in (release,status): f.unlink(missing_ok=True)
