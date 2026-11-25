import os,sys,uuid,time,tempfile,subprocess,requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncRelayAuthorization
from app.models.proof_transport_capability import ProofTransportCapability
from app.services.central_sync_service import CentralSyncService
from sqlalchemy.engine import make_url

BASE=make_url(settings.database_url)
DB_NAME=os.environ.get('STAGE5_B_DB_NAME')
if not DB_NAME:
 raise RuntimeError('STAGE5_B_DB_NAME is required; refusing to use the demo database')
DB=BASE.set(database=DB_NAME).render_as_string(hide_password=False)
ROOT=str(Path(__file__).resolve().parents[1]); old_port=0; new_port=0; procs=[]
def free_port():
 import socket
 s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
def start(port, versions, app_name, pause=None, release=None):
 env={**os.environ,'DATABASE_URL':DB,'PROOF_TRANSPORT_SUPPORTED_VERSIONS':versions,'PGAPPNAME':app_name}
 if pause: env.update(PROOF_CAPABILITY_TEST_HOOK='1',PROOF_CAPABILITY_PAUSE_FILE=pause,PROOF_CAPABILITY_RELEASE_FILE=release,PROOF_CAPABILITY_HOOK_TIMEOUT='20')
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 dev,origin,gen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); secret=uuid.uuid4().hex; scope='b-'+uuid.uuid4().hex[:8]
 with Session(create_engine(DB)) as db:
  db.add(SyncDevice(uuid=dev,installation_uuid=uuid.uuid4(),device_code='b-'+dev.hex[:8],device_name='b',registered_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),is_active=True,central_secret_hash=CentralSyncService()._hash_secret(secret)))
  db.add(SyncRelayAuthorization(carrier_device_uuid=dev,origin_device_uuid=origin,origin_generation_uuid=gen,destination_device_uuid=dev,channel=scope,created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),is_active=True)); db.commit()
 old_port,new_port=free_port(),free_port(); pause=str(Path(tempfile.gettempdir())/('proof-b-pause-'+uuid.uuid4().hex)); release=str(Path(tempfile.gettempdir())/('proof-b-release-'+uuid.uuid4().hex));
 old_app='proof-b-old-'+uuid.uuid4().hex[:8]; new_app='proof-b-new-'+uuid.uuid4().hex[:8]
 procs=[start(old_port,'1',old_app,pause,release),start(new_port,'',new_app,None,None)]
 for p,pr in [(old_port,procs[0]),(new_port,procs[1])]:
  end=time.time()+20
  while time.time()<end:
   try:
    if requests.get(f'http://127.0.0.1:{p}/openapi.json',timeout=1).status_code==200: break
   except Exception: pass
   time.sleep(.1)
 headers={'X-Sync-Device-UUID':str(dev),'X-Sync-Device-Secret':secret}; body={'peer_device_uuid':str(dev),'connection_scope':scope,'origin_device_uuid':str(origin),'origin_generation_uuid':str(gen),'supported_versions':[1]}
 def post(port): return requests.post(f'http://127.0.0.1:{port}/api/v1/sync/v2/proof-capabilities',json=body,headers=headers,timeout=20)
 with ThreadPoolExecutor(max_workers=2) as pool:
  f1=pool.submit(post,old_port)
  while not Path(pause).exists():
   if f1.done(): raise RuntimeError('old request did not reach hook')
   time.sleep(.02)
  f2=pool.submit(post,new_port)
  end=time.time()+10; observed=False
  while time.time()<end:
   with create_engine(DB).connect() as q:
    rows=q.execute(text("""select pid,application_name,datname,wait_event_type,wait_event,state,query,pg_blocking_pids(pid) as blocking_pids from pg_stat_activity where datname=current_database() and application_name=:app and wait_event is not null"""), {'app':new_app}).mappings().all()
    old_rows=q.execute(text("select pid from pg_stat_activity where datname=current_database() and application_name=:app"), {'app':old_app}).scalars().all()
    if rows and any(x['wait_event_type']=='Lock' and x['wait_event']=='advisory' and set(x['blocking_pids']).intersection(old_rows) for x in rows):
     print('lock_wait=',[dict(x) for x in rows], 'old_pids=', old_rows); observed=True; break
   if f2.done(): break
   time.sleep(.02)
  assert observed, 'second request did not show advisory-lock wait'
  Path(release).touch(); r1,r2=f1.result(),f2.result()
 print('old=',r1.status_code,r1.json()); print('new=',r2.status_code,r2.json())
 assert r1.json()['data']['status']=='accepted' and r2.json()['data']['status']=='unsupported'
 assert r2.json()['data']['advertisement_sequence']==r1.json()['data']['advertisement_sequence']+1
 with Session(create_engine(DB)) as db:
  row=db.get(ProofTransportCapability,(dev,scope)); assert row and row.proof_transport_version==0 and row.advertisement_sequence==r2.json()['data']['advertisement_sequence']; print('durable=one version=0 sequence=',row.advertisement_sequence)
finally:
 for p in procs:
  if p.poll() is None: p.terminate(); p.wait(timeout=10)
 for x in locals().get('pause',''),locals().get('release',''):
  try: Path(x).unlink()
  except Exception: pass
