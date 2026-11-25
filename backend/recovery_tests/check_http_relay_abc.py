import os,sys,time,uuid,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncTransportEvent,SyncEventDelivery,SyncEventPublication,SyncPublicationReceipt,SyncTransportCursor,SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
BASE=make_url(settings.database_url); DBS={'A':'ibn_sina_recovery_test','B':'ibn_sina_transport_d','C':os.environ.get('RELAY_TEST_C_DB','ibn_sina_transport_c_4a2d1164')}; PORT={}; CH='abc-'+uuid.uuid4().hex[:8]; SRC,DEV_B,DEV_C,GEN,CLINIC,EID=[uuid.uuid4() for _ in range(6)]; SECRET='stage4-abc-secret'; procs=[]
def choose_ports():
 import socket
 for k in DBS:
  s=socket.socket(); s.bind(('127.0.0.1',0)); PORT[k]=s.getsockname()[1]; s.close()
def url(k): return BASE.set(database=DBS[k])
def url_text(k): return url(k).render_as_string(hide_password=False)
def ep(k): return f'http://127.0.0.1:{PORT[k]}'
def stop(p):
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(5)
  except: p.kill()
def api(k):
 e=os.environ.copy(); e['DATABASE_URL']=url_text(k); log=Path(tempfile.gettempdir())/f'abc-api-{CH}-{k}.log'; return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT[k])],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=log.open('w'),stderr=subprocess.STDOUT)
def ready(p,port,log):
 import socket
 end=time.time()+30
 while time.time()<end:
  if p.poll() is not None: raise RuntimeError(f'api_exited_{p.pid}_{port}')
  try:
   with socket.create_connection(('127.0.0.1',port),.3):
    time.sleep(.2)
    if f'Started server process [{p.pid}]' in log.read_text(errors='replace'): print(f'api_owned pid={p.pid} port={port}'); return
  except OSError: time.sleep(.2)
 raise RuntimeError(f'api_not_owned_{p.pid}_{port}')
def run_worker(db,peer,target,source,worker_id,extra=None):
 e={**os.environ,'DATABASE_URL':url_text(db),'WORKER_PEER':str(peer),'WORKER_CHANNEL':CH,'WORKER_TARGET':target,'WORKER_SOURCE':source,'WORKER_SECRET':SECRET,'WORKER_ID':worker_id,'WORKER_PUBLISHER_DEVICE':str(SRC if db=='A' else DEV_B),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC),'WORKER_CARRIER':str(peer)}; e.update(extra or {})
 p=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); procs.append(p); return p
try:
 choose_ports()
 for k in DBS: 
  with create_engine(url(k)).connect() as c:
   ident=c.execute(text('select current_database(),current_schema(),current_user')).one(); rev=c.execute(text('select version_num from alembic_version')).scalar(); print(k,ident[0],ident[1],rev); assert ident[0]==DBS[k] and rev=='20261008_15'
 h=CentralSyncService()._hash_secret(SECRET)
 for k in DBS:
  with Session(create_engine(url(k))) as db:
   for d in (SRC,DEV_B,DEV_C):
    if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==d)): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='abc-'+d.hex,device_name='abc',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
   db.commit()
 with Session(create_engine(url('A'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_B,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_B,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); payload={'synthetic_abc':EID.hex}; db.add(SyncChange(change_uuid=EID,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=SRC,source_generation_uuid=GEN,source_sequence=9001,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit(); SyncTransportService().publish_committed(db,channel=CH,limit=10,source_device_uuid=SRC,source_generation_uuid=GEN,source_clinic_uuid=CLINIC); SyncTransportService().queue_for_peer(db,peer_device_uuid=DEV_B,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=SRC,limit=10)
 with Session(create_engine(url('B'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_B,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_B,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_B,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_C,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_C,origin_device_uuid=DEV_B,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 with Session(create_engine(url('C'))) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_B,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_C,origin_device_uuid=SRC,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=DEV_C,origin_device_uuid=DEV_B,origin_generation_uuid=GEN,destination_device_uuid=DEV_C,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 for k in DBS:
  p=api(k); procs.append(p); ready(p,PORT[k],Path(tempfile.gettempdir())/f'abc-api-{CH}-{k}.log')
 wa=run_worker('A',DEV_B,ep('B'),ep('A'),'abc-a')
 try: assert wa.wait(30)==0
 except subprocess.TimeoutExpired:
  wa.kill(); print('worker_a_timeout stderr=',wa.stderr.read(4000)); raise
 scenario=os.environ.get('RELAY_RESUME_SCENARIO')
 end=time.time()+30; interrupted=False
 while time.time()<end:
  env={**os.environ,'DATABASE_URL':url_text('B'),'WORKER_PEER':str(DEV_C),'WORKER_CHANNEL':CH,'WORKER_TARGET':ep('C'),'WORKER_SOURCE':ep('B'),'WORKER_SECRET':SECRET,'WORKER_ID':'abc-relay','WORKER_RELAY':'1','RELAY_CARRIER':str(DEV_B),'RELAY_PUBLISHER':str(DEV_B),'RELAY_GENERATION':str(GEN),'RELAY_DESTINATION':str(DEV_C),'WORKER_PUBLISHER_DEVICE':str(DEV_B),'WORKER_PUBLISHER_GENERATION':str(GEN),'WORKER_PUBLISHER_CLINIC':str(CLINIC)}
  if scenario in ('before_relay','after_publish') and not interrupted:
   marker=Path(tempfile.gettempdir())/f'abc-{CH}-{scenario}.json'; release=Path(tempfile.gettempdir())/f'abc-{CH}-{scenario}.release'; marker.unlink(missing_ok=True); release.unlink(missing_ok=True)
   if scenario=='before_relay': env['RELAY_BEFORE_RELAY_PAUSE_FILE']=str(marker); env['RELAY_BEFORE_RELAY_RELEASE_FILE']=str(release)
   else: env['RELAY_AFTER_PUBLISH_PAUSE_FILE']=str(marker); env['RELAY_AFTER_PUBLISH_RELEASE_FILE']=str(release)
   rp=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); procs.append(rp)
   deadline=time.time()+20
   while time.time()<deadline and not marker.exists(): time.sleep(.1)
   if not marker.exists(): raise RuntimeError('relay_coordination_timeout_'+scenario)
   with Session(create_engine(url('B'))) as db:
    bpub=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID,SyncEventPublication.publisher_device_uuid==DEV_B)); bdel=db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_C,SyncEventDelivery.channel==CH)); print('PAUSE_ASSERT',scenario,'publication=',bpub,'delivery=',bdel)
    if scenario=='before_relay': assert bpub==0 and bdel==0
    else: assert bpub==1 and bdel==0
   rp.kill(); rp.wait(10); interrupted=True
  else:
   r=subprocess.run([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=env,text=True,capture_output=True); print('relay_run',r.returncode,r.stdout[-500:],r.stderr[-500:])
  with Session(create_engine(url('B'))) as db:
   published_now=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID,SyncEventPublication.publisher_device_uuid==DEV_B))==1
   delivered_setup=db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_C,SyncEventDelivery.channel==CH))==1
   if published_now and (scenario != 'after_publish' or delivered_setup): break
  time.sleep(.5)
 wb=run_worker('B',DEV_C,ep('C'),ep('B'),'abc-b',{'WORKER_CARRIER':str(DEV_B)}); rc=wb.wait(30); print('worker_b_stderr',wb.stderr.read()[-2000:]); assert rc==0
 # Re-run the real relay one-shot several times: durable publication and
 # delivery counts must remain stable (no relay loop).
 with Session(create_engine(url('B'))) as db:
  before=(db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID,SyncEventPublication.publisher_device_uuid==DEV_B)), db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_C,SyncEventDelivery.channel==CH)))
 for _ in range(3):
  rr=subprocess.run([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=env,text=True,capture_output=True); assert rr.returncode==0
 with Session(create_engine(url('B'))) as db:
  after=(db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID,SyncEventPublication.publisher_device_uuid==DEV_B)), db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_C,SyncEventDelivery.channel==CH)))
  print('RELAY_STABILITY before=',before,'after=',after); assert before==after==(1,1)
 with Session(create_engine(url('A'))) as db: assert db.scalar(select(SyncEventDelivery.status).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_B,SyncEventDelivery.channel==CH))=='delivered'
 with Session(create_engine(url('B'))) as db:
  bi=db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID)); drow=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EID,SyncEventDelivery.peer_device_uuid==DEV_C,SyncEventDelivery.channel==CH)); pubs=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==EID,SyncEventPublication.publisher_device_uuid==DEV_B)); print('diagnostic B inbox=',bi,'B_to_C_status=',drow.status if drow else None,'error=',drow.last_error_code if drow else None,'B_pub=',pubs); print('diagnostic C_api_log=',(Path(tempfile.gettempdir())/f'abc-api-{CH}-C.log').read_text()[-2500:]); assert bi==1 and drow and drow.status=='delivered'
 with Session(create_engine(url('C'))) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EID))==1 and db.scalar(select(func.count()).select_from(MedicalVisit))==0
 print('PASS A->B->C delivered; inbox B/C=1; no medical application')
finally:
 for p in reversed(procs): stop(p)
