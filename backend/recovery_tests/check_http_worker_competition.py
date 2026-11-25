import os,sys,subprocess,time,uuid,tempfile
import threading, queue
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncEventDelivery,SyncEventPublication,SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
B=make_url(settings.database_url);A=B.render_as_string(hide_password=False);D=B.set(database='ibn_sina_transport_d').render_as_string(hide_password=False)
src,peer,gen,clinic,pub,pgen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4();secret='stage4-worker-secret';channel='wrk-'+src.hex[:8];ids=[]
def seed(url):
 with Session(create_engine(url)) as db:
  h=CentralSyncService()._hash_secret(secret)
  for x in (src,peer):
   dev=db.scalar(select(SyncDevice).where(SyncDevice.uuid==x))
   if dev is None:
    db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='wrk-'+x.hex,device_name='wrk',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
   else:
    dev.central_secret_hash=h; dev.is_active=True
  db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
def api(url,p):
 e=os.environ.copy();e['DATABASE_URL']=url
 log=open(str(Path(tempfile.gettempdir())/f'api-{p}-competition.log'),'w',encoding='utf-8')
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=log,text=True)
def worker(env,pause=False):
 e=os.environ.copy();e.update(env)
 if pause:e['WORKER_PAUSE']='1'
 return subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
ps=[]
try:
 seed(A);seed(D)
 with Session(create_engine(D)) as check:
  from app.services.central_sync_service import CentralSyncService as _CSS
  peer_row=check.scalar(select(SyncDevice).where(SyncDevice.uuid==peer)); src_row=check.scalar(select(SyncDevice).where(SyncDevice.uuid==src))
  print('credential_check peer_exists=',peer_row is not None,'peer_active=',bool(peer_row and peer_row.is_active),'peer_secret_match=',bool(peer_row and peer_row.central_secret_hash==_CSS()._hash_secret(secret)),'source_exists=',src_row is not None,'source_active=',bool(src_row and src_row.is_active),'source_secret_match=',bool(src_row and src_row.central_secret_hash==_CSS()._hash_secret(secret)),flush=True)
 with Session(create_engine(A)) as db:
  before=db.scalar(select(func.count()).select_from(MedicalVisit))
  for i in range(5):
   x=uuid.uuid4();ids.append(x);p={'synthetic_worker_id':x.hex};db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=i+1,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
  db.commit()
 db=Session(create_engine(A));
 if db.scalar(select(SyncDevice).where(SyncDevice.uuid==peer)) is None:
  h=CentralSyncService()._hash_secret(secret);db.add(SyncDevice(uuid=peer,installation_uuid=uuid.uuid4(),device_code='wrk-peer-'+peer.hex[:8],device_name='wrk',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h));db.commit()
 s=SyncTransportService()
 deadline=time.time()+90
 while time.time()<deadline:
  s.publish_committed(db,channel=channel,limit=1000,source_device_uuid=src,source_generation_uuid=gen,source_clinic_uuid=clinic,publisher_device_uuid=pub,publisher_generation_uuid=pgen)
  published=db.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid.in_(ids),SyncEventPublication.channel==channel))
  print(f"fixture publication progress={published}/{len(ids)}", flush=True)
  if published==len(ids): break
 assert published==len(ids), "test events were not all published"
 queued=s.queue_for_peer(db,peer_device_uuid=peer,channel=channel,source_clinic_uuid=clinic,source_generation_uuid=gen,source_device_uuid=src,limit=100)
 assert queued["queued"]==len(ids)
 print(f"fixture publication_rows={published} eligible_deliveries={queued['queued']} channel={channel}")
 ps=[api(A,8891),api(D,8892)];time.sleep(4)
 env={'DATABASE_URL':A,'WORKER_PEER':str(peer),'WORKER_CHANNEL':channel,'WORKER_TARGET':'http://127.0.0.1:8892','WORKER_SOURCE':'http://127.0.0.1:8891','WORKER_SECRET':secret}
 env['WORKER_LEASE_SECONDS']='30';env['WORKER_PUBLISHER_DEVICE']=str(pub);env['WORKER_PUBLISHER_GENERATION']=str(pgen);env['WORKER_PUBLISHER_CLINIC']=str(clinic);env['WORKER_CARRIER']=str(peer)
 import tempfile, pathlib
 import time as _time, json
 gates=[str(pathlib.Path(tempfile.gettempdir())/(f'worker-gate-{channel}-{i}')) for i in (1,2)]
 logs=[str(pathlib.Path(tempfile.gettempdir())/(f'worker-log-{channel}-{i}')) for i in (1,2)]
 statuses=[str(pathlib.Path(tempfile.gettempdir())/(f'worker-status-{channel}-{i}')) for i in (1,2)]
 for f in gates+logs+statuses: pathlib.Path(f).unlink(missing_ok=True)
 env['WORKER_COORDINATE']='1'; env['WORKER_LEASE_SECONDS']='30'; env['WORKER_CLAIM_LOG']=logs[0]; env['WORKER_RELEASE_FILE']=gates[0]; env['WORKER_STATUS_FILE']=statuses[0]; env['WORKER_ID']='one'; w1=worker(env)
 env2=env.copy(); env2['WORKER_CLAIM_LOG']=logs[1]; env2['WORKER_RELEASE_FILE']=gates[1]; env2['WORKER_STATUS_FILE']=statuses[1]; env2['WORKER_ID']='two'; w2=worker(env2)
 deadline=time.time()+15
 while (not w1.poll() is None or not w2.poll() is None) and time.time()<deadline:
  if w1.poll() is not None or w2.poll() is not None: break
  if pathlib.Path(logs[0]).exists() and pathlib.Path(logs[1]).exists():
   if pathlib.Path(logs[0]).stat().st_size or pathlib.Path(logs[1]).stat().st_size: break
  time.sleep(.1)
 q1,q2=queue.Queue(),queue.Queue()
 threading.Thread(target=lambda:q1.put(w1.stdout.readline().strip()),daemon=True).start()
 threading.Thread(target=lambda:q2.put(w2.stdout.readline().strip()),daemon=True).start()
 try: line1=q1.get(timeout=15)
 except queue.Empty: line1=""
 try: line2=q2.get(timeout=15)
 except queue.Empty: line2=""
 if not line1.startswith('CLAIMED ') or not line2.startswith('CLAIMED '):
  raise AssertionError(f"after_claim missing: worker1={line1!r} worker2={line2!r} stderr1={w1.stderr.read(2000)!r} stderr2={w2.stderr.read(2000)!r}")
 for p in ps: pass
 with Session(create_engine(A)) as db:
  claimed=db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids),SyncEventDelivery.status=='sending')).all(); assert len(claimed)>=4
  assert len({x.event_uuid for x in claimed})==len(claimed); assert all(x.lease_token and x.lease_expires_at>datetime.now(timezone.utc) for x in claimed)
 pathlib.Path(gates[0]).touch(); pathlib.Path(gates[1]).touch(); w1.wait(30); w2.wait(30)
 print(w1.stderr.read()); print(w2.stderr.read())
 env.pop('WORKER_COORDINATE',None); env.pop('WORKER_LEASE_SECONDS',None)
 with Session(create_engine(A)) as db:
  delivered=db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids),SyncEventDelivery.status=='delivered')); print('delivered',delivered); print([(str(x.event_uuid),x.status,x.last_error_code) for x in db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids))).all()]); assert delivered==5
  assert len({x.lease_token for x in db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids))).all() if x.lease_token}) == 5
 with Session(create_engine(D)) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==5;assert db.scalar(select(func.count()).select_from(MedicalVisit))==0
 print('PASS concurrent workers claimed disjoint events and completed HTTP delivery')
finally:
 for p in ps:
  p.terminate()
  try:p.wait(timeout=5)
  except: p.kill()
