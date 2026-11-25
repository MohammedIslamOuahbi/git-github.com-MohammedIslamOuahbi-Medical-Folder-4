"""Stage-four durable A->B->C->A relay-loop test; transport only."""
import os,sys,time,uuid,subprocess,socket,tempfile
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization,SyncEventPublication,SyncEventDelivery,SyncEventInbox,SyncTransportEvent
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
from sqlalchemy.engine import make_url

BASE=make_url(settings.database_url); DBS={'A':'ibn_sina_recovery_test','B':'ibn_sina_transport_d','C':os.environ.get('RELAY_TEST_C_DB','ibn_sina_transport_c_4a2d1164')}; PORT={}; RUN=uuid.uuid4().hex[:10]; CH='loop-'+RUN; CLINIC=uuid.uuid4(); GEN=uuid.uuid4(); ADEV,BDEV,CDEV=[uuid.uuid4() for _ in range(3)]; EID=uuid.uuid4(); SECRET='stage4-loop-secret'; procs=[]
def url(k): return BASE.set(database=DBS[k])
def txt(k): return url(k).render_as_string(hide_password=False)
def ep(k): return f'http://127.0.0.1:{PORT[k]}'
def stop(p):
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(5)
  except: p.kill()
def choose_ports():
 for k in DBS:
  s=socket.socket(); s.bind(('127.0.0.1',0)); PORT[k]=s.getsockname()[1]; s.close()
def api(k):
 log=Path(tempfile.gettempdir())/f'loop-{RUN}-{k}.log'; e={**os.environ,'DATABASE_URL':txt(k)}
 p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT[k])],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=log.open('w'),stderr=subprocess.STDOUT); procs.append(p); return p,log
def ready(p,log):
 end=time.time()+30
 while time.time()<end:
  if p.poll() is not None: raise RuntimeError(f'api_exited_{p.pid}')
  try:
   with socket.create_connection(('127.0.0.1',PORT[next(k for k,v in PORT.items() if v==int(log.stem.split("-")[-1]) if False)]),.1): pass
  except Exception: pass
  if f'Started server process [{p.pid}]' in log.read_text(errors='replace'): return
  time.sleep(.2)
 raise RuntimeError(f'api_not_owned_{p.pid}')
def worker(db,peer,target,source,wid,relay=False,publisher=None,dest=None,carrier=None):
 e={**os.environ,'DATABASE_URL':txt(db),'WORKER_PEER':str(peer),'WORKER_CHANNEL':CH,'WORKER_TARGET':target,'WORKER_SOURCE':source,'WORKER_SECRET':SECRET,'WORKER_ID':wid,'WORKER_CARRIER':str(carrier or peer),'WORKER_PUBLISHER_DEVICE':str(publisher or (ADEV if db=='A' else BDEV)),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC)}
 if relay: e.update(WORKER_RELAY='1',RELAY_CARRIER=str(publisher),RELAY_PUBLISHER=str(publisher),RELAY_GENERATION=str(GEN),RELAY_DESTINATION=str(dest),RELAY_LIMIT='2')
 return subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def b_state():
 with Session(create_engine(url('B'))) as db:
  ev=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==EID)); te=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==EID))
  pubs=db.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==EID)).all(); dels=db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID)).all()
  auth=db.scalar(select(SyncRelayAuthorization.id).where(SyncRelayAuthorization.carrier_device_uuid==BDEV,SyncRelayAuthorization.origin_device_uuid==ADEV,SyncRelayAuthorization.destination_device_uuid==CDEV,SyncRelayAuthorization.channel==CH,SyncRelayAuthorization.is_active.is_(True)))
  print('B_STATE', 'inbox=',bool(ev), 'transport=',bool(te), 'origin_kind=',te.origin_kind if te else None, 'source=',str(te.source_device_uuid) if te else None, 'pubs=',[(str(p.publisher_device_uuid),p.publish_sequence) for p in pubs], 'deliveries=',[(str(d.peer_device_uuid),str(d.publisher_device_uuid),d.status,d.last_error_code) for d in dels], 'auth_B_to_C=',bool(auth))
try:
 choose_ports()
 for k in DBS:
  with create_engine(url(k)).connect() as c: assert c.execute(text('select current_database()')).scalar()==DBS[k] and c.execute(text('select version_num from alembic_version')).scalar()=='20261008_15'
 h=CentralSyncService()._hash_secret(SECRET)
 for k in DBS:
  with Session(create_engine(url(k))) as db:
   for d in (ADEV,BDEV,CDEV):
    db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='loop-'+d.hex,device_name='loop',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
   db.commit()
 # Authorize each receive/relay edge; no transport rows are written by this fixture.
 with Session(create_engine(url('A'))) as db:
  p={'loop_event':EID.hex}; db.add(SyncChange(change_uuid=EID,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=CLINIC,source_device_uuid=ADEV,source_generation_uuid=GEN,source_sequence=1,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit(); SyncTransportService().publish_committed(db,channel=CH,source_device_uuid=ADEV,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=ADEV,publisher_generation_uuid=GEN); SyncTransportService().queue_for_peer(db,peer_device_uuid=BDEV,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=ADEV)
 for k in DBS:
  with Session(create_engine(url(k))) as db:
   for carrier,origin,dest in ((BDEV,ADEV,BDEV),(BDEV,ADEV,CDEV),(CDEV,ADEV,CDEV),(CDEV,ADEV,ADEV),(ADEV,ADEV,ADEV),(ADEV,BDEV,ADEV),(CDEV,BDEV,CDEV),(ADEV,CDEV,ADEV),(CDEV,BDEV,ADEV)):
    db.add(SyncRelayAuthorization(carrier_device_uuid=carrier,origin_device_uuid=origin,origin_generation_uuid=GEN,destination_device_uuid=dest,channel=CH,created_at=datetime.now(timezone.utc),is_active=True))
   db.commit()
 for k in DBS:
  p,log=api(k); ready(p,log)
 # A->B, then relay B->C, then relay C->A.
 for db,peer,src,dst,pub in (('A',BDEV,'A','B',ADEV),('B',CDEV,'B','C',BDEV),('C',ADEV,'C','A',CDEV)):
  if src=='B': b_state()
  if db=='A': p=worker(db,peer,ep(dst),ep(src),f'loop-{src}-{dst}'); procs.append(p)
  else:
   # relay_inbox_once is one bounded durable pass; repeat passes to prove
   # progress is state-driven and not dependent on one process invocation.
   for attempt in range(3):
    p=worker(db,peer,ep(dst),ep(src),f'loop-{src}-{dst}-{attempt}',relay=True,publisher=pub,dest=peer); procs.append(p)
    rc=p.wait(45); out=p.stdout.read()[-1500:]; err=p.stderr.read()[-1500:]; print(f'edge {src}->{dst} pass={attempt} rc={rc} stdout={out} stderr={err}'); b_state(); assert rc==0
   # Relay promotion and network delivery are separate worker phases.
   p=worker(db,peer,ep(dst),ep(src),f'loop-send-{src}-{dst}',publisher=pub,carrier=peer); procs.append(p)
   rc=p.wait(45); out=p.stdout.read()[-1200:]; err=p.stderr.read()[-1200:]; print(f'edge {src}->{dst} send rc={rc} stdout={out} stderr={err}'); assert rc==0
   continue
  rc=p.wait(45); err=p.stderr.read()[-1500:]; print(f'edge {src}->{dst} rc={rc} stderr={err}'); assert rc==0
 with Session(create_engine(url('A'))) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==BDEV,SyncEventDelivery.channel==CH)); print('edge A->B',d.status if d else None); assert d and d.status=='delivered'
 with Session(create_engine(url('B'))) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==CDEV,SyncEventDelivery.channel==CH)); assert d and d.status=='delivered'; print('edge B->C',d.status)
 with Session(create_engine(url('C'))) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==ADEV,SyncEventDelivery.channel==CH)); assert d and d.status=='delivered'; print('edge C->A',d.status)
 def counts():
  out=[]
  for k in DBS:
   with Session(create_engine(url(k))) as db:
    out.append((k,db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID)),db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID)),db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))))
  return out
 stable_before=counts()
 # Durable repeat passes after all edges are complete; no in-memory state is reused.
 for _ in range(2):
  for db,peer,src,dst,pub in (('B',CDEV,'B','C',BDEV),('C',ADEV,'C','A',CDEV)):
   p=worker(db,peer,ep(dst),ep(src),f'repeat-{src}-{dst}',relay=True,publisher=pub,dest=peer); procs.append(p); assert p.wait(45)==0
   p=worker(db,peer,ep(dst),ep(src),f'repeat-send-{src}-{dst}',publisher=pub,carrier=peer); procs.append(p); assert p.wait(45)==0
 stable_after=counts(); print('LOOP_STABILITY before=',stable_before,'after=',stable_after); assert stable_before==stable_after
 # New B publication delivery to A is queued by the service, then transported normally.
 with Session(create_engine(url('B'))) as db:
  q=SyncTransportService().queue_for_peer(db,peer_device_uuid=ADEV,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=ADEV,limit=10); print('B_TO_A_QUEUE',q)
  pubs=db.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==EID)).all(); dels=db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID)).all(); print('B_TO_A_STATE',[(str(x.publisher_device_uuid),x.publish_sequence) for x in pubs],[(str(x.peer_device_uuid),str(x.publisher_device_uuid),x.status,x.last_error_code) for x in dels])
 p=worker('B',ADEV,ep('A'),ep('B'),'new-destination-B-A',publisher=BDEV,carrier=ADEV); procs.append(p); rc=p.wait(45); print('B_TO_A_WORKER',rc,p.stdout.read()[-1500:],p.stderr.read()[-1500:]); assert rc==0
 with Session(create_engine(url('B'))) as db:
  d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==ADEV,SyncEventDelivery.publisher_device_uuid==BDEV,SyncEventDelivery.channel==CH)); assert d and d.status=='delivered'; print('new_destination B->A',d.status)
 print('PASS relay loop; event=',EID,'run=',RUN,'no medical apply')
finally:
 for p in reversed(procs): stop(p)
