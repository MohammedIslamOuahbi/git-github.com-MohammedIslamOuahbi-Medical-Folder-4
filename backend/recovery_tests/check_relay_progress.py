import os, sys, time, uuid, subprocess, socket, tempfile
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization, SyncEventPublication, SyncEventDelivery, SyncEventInbox, SyncTransportEvent
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService

BASE=make_url(settings.database_url); DBS={'A':'ibn_sina_recovery_test','B':'ibn_sina_transport_d','C':os.environ.get('RELAY_TEST_C_DB','ibn_sina_transport_c_4a2d1164')}; PORT={}; CH='progress-'+uuid.uuid4().hex[:8]; CLINIC=uuid.uuid4(); GEN=uuid.uuid4(); U=uuid.uuid4(); V=uuid.uuid4(); BDEV=uuid.uuid4(); CDEV=uuid.uuid4(); SECRET='stage4-progress-secret'; procs=[]
def choose_ports():
 for k in DBS:
  s=socket.socket(); s.bind(('127.0.0.1',0)); PORT[k]=s.getsockname()[1]; s.close()
def url(k): return BASE.set(database=DBS[k])
def txt(k): return url(k).render_as_string(hide_password=False)
def ep(k): return f'http://127.0.0.1:{PORT[k]}'
def stop(p):
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(5)
  except: p.kill()
def ready(p,port,log):
 end=time.time()+30
 while time.time()<end:
  if p.poll() is not None: raise RuntimeError(f'api_exited_{p.pid}_{port}')
  try:
   with socket.create_connection(('127.0.0.1',port),.3):
    time.sleep(.2)
    if f'Started server process [{p.pid}]' in log.read_text(errors='replace'): print(f'api_owned pid={p.pid} port={port}'); return
  except OSError: time.sleep(.2)
 raise RuntimeError(f'api_not_owned_{p.pid}_{port}')
def api(k):
 e={**os.environ,'DATABASE_URL':txt(k)}; log=Path(tempfile.gettempdir())/f'progress-{CH}-{k}.log'; p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT[k])],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=log.open('w'),stderr=subprocess.STDOUT); procs.append(p); return p
def worker(db,peer,target,source,wid,extra=None):
 e={**os.environ,'DATABASE_URL':txt(db),'WORKER_PEER':str(peer),'WORKER_CHANNEL':CH,'WORKER_TARGET':target,'WORKER_SOURCE':source,'WORKER_SECRET':SECRET,'WORKER_ID':wid,'WORKER_PUBLISHER_DEVICE':str(BDEV if db=='B' else U),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC),'WORKER_CARRIER':str(peer)}; e.update(extra or {})
 p=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); procs.append(p); return p
EIDS=[]
try:
 choose_ports()
 for k in DBS:
  with create_engine(url(k)).connect() as c:
   assert c.execute(text('select current_database()')).scalar()==DBS[k]; assert c.execute(text('select version_num from alembic_version')).scalar()=='20261008_15'
 h=CentralSyncService()._hash_secret(SECRET)
 for k in DBS:
  with Session(create_engine(url(k))) as db:
   for d in (U,V,BDEV,CDEV):
    if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==d)): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='progress-'+d.hex,device_name='progress',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
   db.commit()
 # B accepts both origins, but only V is authorized to relay to C.
 with Session(create_engine(url('A'))) as db:
  for origin in [U]*5+[V]*3:
   eid=uuid.uuid4(); EIDS.append((eid,origin)); payload={'progress_event':eid.hex}; db.add(SyncChange(change_uuid=eid,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=origin,source_generation_uuid=GEN,source_sequence=1000+len(db.new),schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
  db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=U,origin_generation_uuid=GEN,destination_device_uuid=BDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=BDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
  SyncTransportService().publish_committed(db,channel=CH,limit=20,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=U,publisher_generation_uuid=GEN); SyncTransportService().queue_for_peer(db,peer_device_uuid=BDEV,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=U,limit=20); SyncTransportService().queue_for_peer(db,peer_device_uuid=BDEV,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=V,limit=20)
 with Session(create_engine(url('B'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=U,origin_generation_uuid=GEN,destination_device_uuid=BDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=BDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=CDEV,origin_device_uuid=BDEV,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True));
  db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=CDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 with Session(create_engine(url('C'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=CDEV,origin_device_uuid=V,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 for k in DBS:
  p=api(k); ready(p,PORT[k],Path(tempfile.gettempdir())/f'progress-{CH}-{k}.log')
 wa=worker('A',BDEV,ep('B'),ep('A'),'progress-a',{'WORKER_BATCH_SIZE':'1','WORKER_CYCLES':'8'}); assert wa.wait(40)==0; print('worker_a_stderr',wa.stderr.read()[-2000:])
 with Session(create_engine(url('B'))) as db:
  for eid, origin in EIDS:
   ev=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==eid)); auth=db.scalar(select(SyncRelayAuthorization.id).where(SyncRelayAuthorization.carrier_device_uuid==BDEV,SyncRelayAuthorization.origin_device_uuid==origin,SyncRelayAuthorization.origin_generation_uuid==GEN,SyncRelayAuthorization.destination_device_uuid==CDEV,SyncRelayAuthorization.channel==CH,SyncRelayAuthorization.is_active.is_(True))); print('EVENT_CHECK',eid, 'inbox=',bool(db.scalar(select(SyncEventInbox.id).where(SyncEventInbox.event_uuid==eid))), 'transport=',bool(ev), 'origin_kind=',ev.origin_kind if ev else None, 'source=',ev.source_device_uuid if ev else None, 'gen=',ev.source_generation_uuid if ev else None, 'auth=',bool(auth))
 # Repeated real one-shot relay runs with limit 2. Unauthorized U events remain.
 relay_env={**os.environ,'DATABASE_URL':txt('B'),'WORKER_PEER':str(CDEV),'WORKER_CHANNEL':CH,'WORKER_TARGET':ep('C'),'WORKER_SOURCE':ep('B'),'WORKER_SECRET':SECRET,'WORKER_ID':'progress-relay','WORKER_RELAY':'1','RELAY_CARRIER':str(BDEV),'RELAY_PUBLISHER':str(BDEV),'RELAY_GENERATION':str(GEN),'RELAY_DESTINATION':str(CDEV),'RELAY_LIMIT':'2','WORKER_PUBLISHER_DEVICE':str(BDEV),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC)}
 for _ in range(12):
  r=subprocess.run([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=relay_env,capture_output=True,text=True); print('relay',r.returncode,r.stderr[-300:]); assert r.returncode==0
 wb=worker('B',CDEV,ep('C'),ep('B'),'progress-b',{'WORKER_CARRIER':str(BDEV),'WORKER_CYCLES':'8'}); assert wb.wait(40)==0; print('worker_b_stderr',wb.stderr.read()[-3000:])
 with Session(create_engine(url('B'))) as db:
  rows=[]
  for eid, origin in EIDS:
   pub=db.scalar(select(SyncEventPublication).where(SyncEventPublication.event_uuid==eid,SyncEventPublication.publisher_device_uuid==BDEV,SyncEventPublication.publisher_generation_uuid==GEN,SyncEventPublication.channel==CH))
   d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==eid,SyncEventDelivery.peer_device_uuid==CDEV,SyncEventDelivery.channel==CH))
   rows.append((str(eid), origin==V, bool(pub), d.status if d else None))
  print('EVENT_TABLE',rows)
  assert all((not allowed and not pub and status is None) or (allowed and pub and status in ('pending','sending','delivered')) for _,allowed,pub,status in rows)
  assert sum(1 for _,allowed,pub,status in rows if allowed and pub)==3
 # New authorized event after the first eight: create locally, publish and
 # queue through the normal source service, then transfer over HTTP.
 new_id=uuid.uuid4()
 with Session(create_engine(url('A'))) as db:
  payload={'progress_new_event':new_id.hex}; db.add(SyncChange(change_uuid=new_id,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=V,source_generation_uuid=GEN,source_sequence=90000,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit(); SyncTransportService().publish_committed(db,channel=CH,limit=2,source_device_uuid=V,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=U,publisher_generation_uuid=GEN); SyncTransportService().queue_for_peer(db,peer_device_uuid=BDEV,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=V,limit=2)
 wa2=worker('A',BDEV,ep('B'),ep('A'),'progress-a2',{'WORKER_BATCH_SIZE':'1','WORKER_CYCLES':'1'}); assert wa2.wait(30)==0
 for _ in range(3): subprocess.run([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=relay_env,check=True)
 wb_new=worker('B',CDEV,ep('C'),ep('B'),'progress-b-new',{'WORKER_CARRIER':str(BDEV),'WORKER_CYCLES':'2'}); assert wb_new.wait(30)==0
 with Session(create_engine(url('B'))) as db:
  npub=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==new_id,SyncEventPublication.publisher_device_uuid==BDEV,SyncEventPublication.publisher_generation_uuid==GEN,SyncEventPublication.channel==CH)); ndel=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==new_id,SyncEventDelivery.peer_device_uuid==CDEV,SyncEventDelivery.channel==CH)); assert npub==1 and ndel and ndel.status=='delivered'; print('NEW_EVENT publication=',npub,'delivery=',ndel.status)
 with Session(create_engine(url('C'))) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==new_id))==1
 # Re-authorize two old U events by origin scope, then relay again.
 with Session(create_engine(url('B'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=BDEV,origin_device_uuid=U,origin_generation_uuid=GEN,destination_device_uuid=CDEV,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 for _ in range(4): subprocess.run([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=relay_env,check=True)
 wb2=worker('B',CDEV,ep('C'),ep('B'),'progress-b2',{'WORKER_CARRIER':str(BDEV)}); assert wb2.wait(40)==0
 with Session(create_engine(url('B'))) as db:
  u_pub2=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.source_device_uuid==U,SyncEventPublication.publisher_device_uuid==BDEV,SyncEventPublication.channel==CH)); total_del=db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.peer_device_uuid==CDEV,SyncEventDelivery.channel==CH)); print('after_reauthorization unauthorized_origin_publications=',u_pub2,'total_B_to_C_deliveries=',total_del); assert u_pub2==5 and total_del==9
 print('PASS relay progress limit=2; later authorized events advanced; reauthorization re-evaluated old events; no medical apply')
finally:
 for p in reversed(procs): stop(p)
