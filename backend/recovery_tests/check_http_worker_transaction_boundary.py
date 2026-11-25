import os,sys,time,json,uuid,subprocess,tempfile,threading
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncEventDelivery,SyncEventPublication,SyncPublicationReceipt,SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
B=make_url(settings.database_url); A=B.render_as_string(hide_password=False); D=B.set(database='ibn_sina_transport_d').render_as_string(hide_password=False)
SRC,PEER,GEN,CLINIC,EID=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); CH='tx-'+SRC.hex[:8]; SECRET='stage4-boundary-secret'; ROOT=Path(tempfile.gettempdir()); gate=ROOT/f'gate-{CH}'; release=ROOT/f'release-{CH}'
procs=[]
def api(url,port):
 e=os.environ.copy();e['DATABASE_URL']=url
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait_port(port):
 import socket
 end=time.time()+20
 while time.time()<end:
  try:
   with socket.create_connection(('127.0.0.1',port),.3): return
  except OSError: time.sleep(.2)
 raise RuntimeError(f'port {port} not ready')
def stop(p):
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(5)
  except: p.kill()
try:
 for f in (gate,release): f.unlink(missing_ok=True)
 h=CentralSyncService()._hash_secret(SECRET)
 for url in (A,D):
  with Session(create_engine(url)) as db:
   for x in (SRC,PEER):
    if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==x)):
     db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='tx-'+x.hex,device_name='boundary',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
   db.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True))
   db.commit()
 payload={'synthetic_boundary':EID.hex};
 with Session(create_engine(A)) as db:
  db.add(SyncChange(change_uuid=EID,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=SRC,source_generation_uuid=GEN,source_sequence=700,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit()
 with Session(create_engine(A)) as db:
  svc=SyncTransportService(); svc.publish_committed(db,channel=CH,limit=100,source_device_uuid=SRC,source_generation_uuid=GEN,source_clinic_uuid=CLINIC); q=svc.queue_for_peer(db,peer_device_uuid=PEER,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=SRC,limit=10); db.commit(); assert q['queued']==1
 with Session(create_engine(A)) as db: assert db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID))==1
 p1=api(A,8901);p2=api(D,8902);procs += [p1,p2];wait_port(8901);wait_port(8902)
 proxy=subprocess.Popen([sys.executable,'recovery_tests/_run_http_gate_proxy.py'],cwd=str(Path(__file__).resolve().parents[1]),env={**os.environ,'PROXY_GATE':str(gate),'PROXY_RELEASE':str(release),'PROXY_TARGET':'http://127.0.0.1:8902','PROXY_PORT':'8903'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);procs.append(proxy);wait_port(8903)
 env={**os.environ,'DATABASE_URL':A,'WORKER_PEER':str(PEER),'WORKER_CHANNEL':CH,'WORKER_TARGET':'http://127.0.0.1:8903','WORKER_SOURCE':'http://127.0.0.1:8901','WORKER_SECRET':SECRET,'WORKER_LEASE_SECONDS':'30','WORKER_ID':'boundary','WORKER_PUBLISHER_DEVICE':str(SRC),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC)}
 w=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);procs.append(w)
 end=time.time()+20
 while not gate.exists() and time.time()<end: time.sleep(.1)
 if not gate.exists():
  print('worker_rc',w.poll(),'stderr',w.stderr.read() if w.poll() is not None else 'running')
  raise AssertionError('proxy did not observe request')
 with Session(create_engine(A)) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.channel==CH)); assert d and d.status=='sending' and d.lease_expires_at>datetime.now(timezone.utc); token=d.lease_token
  locked=db.execute(select(SyncEventDelivery).where(SyncEventDelivery.id==d.id).with_for_update(nowait=True)).scalar_one(); assert locked.id==d.id; db.rollback()
 release.touch(); rc=w.wait(30); assert rc==0, (w.stderr.read()[-2000:])
 with Session(create_engine(A)) as db: assert db.scalar(select(SyncEventDelivery.status).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.channel==CH))=='delivered'
 with Session(create_engine(D)) as db:
  assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))==1
  assert db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==EID,SyncPublicationReceipt.channel==CH))==1
  assert db.scalar(select(func.count()).select_from(MedicalVisit))==0
 print('PASS transaction boundary: proxy gate observed; claim row NOWAIT lock succeeded during HTTP wait; delivered=1 inbox=1 receipt=1 medical_rows=0')
finally:
 for p in reversed(procs): stop(p)
 for f in (gate,release): f.unlink(missing_ok=True)



