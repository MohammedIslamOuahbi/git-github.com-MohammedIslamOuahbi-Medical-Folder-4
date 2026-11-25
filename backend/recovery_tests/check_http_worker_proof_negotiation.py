import os,sys,subprocess,time,uuid
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncEventDelivery,SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
B=make_url(settings.database_url);A=B.set(database='ibn_sina_cap_418ef234').render_as_string(hide_password=False);D=B.set(database='ibn_sina_cap_7d4ae3b9').render_as_string(hide_password=False)
src,peer,gen,clinic,pub,pgen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4();secret='stage4-worker-secret';channel='wrk-'+src.hex[:8];ids=[]
def seed(url):
 with Session(create_engine(url)) as db:
  h=CentralSyncService()._hash_secret(secret)
  for x in (src,peer):
   if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==x)):db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='wrk-'+x.hex,device_name='wrk',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.commit()
def api(url,p):
 e=os.environ.copy();e['DATABASE_URL']=url; e['PROOF_TRANSPORT_SUPPORTED_VERSIONS']=os.environ.get('WORKER_TEST_SERVER_VERSIONS', '' if p==8892 else '1')
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def worker(env,pause=False):
 e=os.environ.copy();e.update(env)
 if pause:e['WORKER_PAUSE']='1'
 return subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
ps=[]
try:
 for dbname,url in (("ibn_sina_cap_418ef234",A),("ibn_sina_cap_7d4ae3b9",D)):
  with create_engine(url).connect() as q: assert q.execute(text('select current_database()')).scalar_one()==dbname and q.execute(text('select version_num from alembic_version')).scalar_one()=='20261008_23'
 seed(A);seed(D)
 with Session(create_engine(D)) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
 with Session(create_engine(A)) as db:
  before=db.scalar(select(func.count()).select_from(MedicalVisit))
  for i in range(5):
   x=uuid.uuid4();ids.append(x);p={'synthetic_worker_id':x.hex};db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=i+1,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
  db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True));db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True));db.commit();s=SyncTransportService();s.publish_committed(db,channel=channel,limit=1000,source_device_uuid=src,source_generation_uuid=gen,source_clinic_uuid=clinic,publisher_device_uuid=pub,publisher_generation_uuid=pgen);s.queue_for_peer(db,peer_device_uuid=peer,channel=channel,source_clinic_uuid=clinic,source_generation_uuid=gen,source_device_uuid=src,limit=100)
 ps=[api(A,8891),api(D,8892)]; print('api_pids=',[p.pid for p in ps]); time.sleep(4)
 env={'DATABASE_URL':A,'WORKER_PEER':str(peer),'WORKER_CHANNEL':channel,'WORKER_TARGET':'http://127.0.0.1:8892','WORKER_SOURCE':'http://127.0.0.1:8891','WORKER_SECRET':secret,'WORKER_PUBLISHER_DEVICE':str(pub),'WORKER_PUBLISHER_GENERATION':str(pgen),'WORKER_PUBLISHER_CLINIC':str(clinic),'WORKER_CARRIER':str(peer)}
 env['WORKER_ORIGIN_DEVICE']=str(src); env['WORKER_ORIGIN_GENERATION']=str(gen)
 env['WORKER_LEASE_SECONDS']='1'; env['WORKER_PAUSE']='1'; env['WORKER_CAPABILITY_TARGET']='http://127.0.0.1:8892'; env['WORKER_CONNECTION_SCOPE']=channel; env['WORKER_CAPABILITY_VERSIONS']='[1]'
 import tempfile, pathlib
 gate=str(pathlib.Path(tempfile.gettempdir())/('worker-gate-'+channel)); pathlib.Path(gate).unlink(missing_ok=True); env['WORKER_COORDINATE']='1'; env['WORKER_RELEASE_FILE']=gate
 paused=worker(env); print('worker_pid=',paused.pid); import time as _time
 line=paused.stdout.readline().strip(); assert line.startswith('CLAIMED '), line
 with Session(create_engine(A)) as db:
  claimed=db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids),SyncEventDelivery.status=='sending')).all(); assert claimed
  old_token=claimed[0].lease_token
 paused.kill(); paused.wait(10)
 pathlib.Path(gate).touch()
 _time.sleep(2)
 env.pop('WORKER_PAUSE',None); env.pop('WORKER_LEASE_SECONDS',None); env.pop('WORKER_COORDINATE',None); env.pop('WORKER_RELEASE_FILE',None); env['WORKER_CAPABILITY_TARGET']='http://127.0.0.1:8892'; env['WORKER_CONNECTION_SCOPE']=channel; env['WORKER_CAPABILITY_VERSIONS']='[1]'
 ws=[worker(env)]; [w.wait(30) for w in ws]
 for w in ws: print(w.stdout.read()); print(w.stderr.read())
 with Session(create_engine(A)) as db:
  delivered=db.scalar(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids),SyncEventDelivery.status=='delivered')); print('delivered',delivered); print([(str(x.event_uuid),x.status,x.last_error_code) for x in db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids))).all()]); assert delivered==5
  assert len({x.lease_token for x in db.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_(ids))).all() if x.lease_token}) == 5
 with Session(create_engine(D)) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==5;assert db.scalar(select(func.count()).select_from(MedicalVisit))==0
 print('PASS worker kill/resume, HTTP receive/ack, one inbox per event, medical isolation')
finally:
 for p in ps:
  p.terminate()
  try:p.wait(timeout=5)
  except: p.kill()







