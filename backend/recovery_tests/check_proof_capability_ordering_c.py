import os,sys,uuid,time,subprocess,requests,socket
from pathlib import Path
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncRelayAuthorization
from app.models.proof_transport_capability import ProofTransportCapability
from app.services.central_sync_service import CentralSyncService
from sqlalchemy.engine import make_url
BASE=make_url(settings.database_url); DB=BASE.set(database='ibn_sina_cap_418ef234').render_as_string(hide_password=False); ROOT=str(Path(__file__).resolve().parents[1]); ps=[]
def port():
 s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
def start(p):
 e={**os.environ,'DATABASE_URL':DB,'PROOF_TRANSPORT_SUPPORTED_VERSIONS':'1'}
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=ROOT,env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 dev,origin,gen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); secret=uuid.uuid4().hex; scope='c-'+uuid.uuid4().hex[:8]
 with Session(create_engine(DB)) as db:
  db.add(SyncDevice(uuid=dev,installation_uuid=uuid.uuid4(),device_code='c-'+dev.hex[:8],device_name='c',registered_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),is_active=True,central_secret_hash=CentralSyncService()._hash_secret(secret)))
  db.add(SyncRelayAuthorization(carrier_device_uuid=dev,origin_device_uuid=origin,origin_generation_uuid=gen,destination_device_uuid=dev,channel=scope,created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),is_active=True)); db.commit()
 with Session(create_engine(DB)) as db:
  previous=db.scalar(select(ProofTransportCapability.advertisement_sequence).where(ProofTransportCapability.peer_device_uuid==dev,ProofTransportCapability.connection_scope==scope)) or 0
 ports=[port(),port()]; ps=[start(x) for x in ports]
 for p in ports:
  end=time.time()+20
  while time.time()<end:
   try:
    if requests.get(f'http://127.0.0.1:{p}/openapi.json',timeout=1).status_code==200: break
   except Exception: pass
  else: raise RuntimeError('API_READY_TIMEOUT')
 body={'peer_device_uuid':str(dev),'connection_scope':scope,'origin_device_uuid':str(origin),'origin_generation_uuid':str(gen),'supported_versions':[1]}; headers={'X-Sync-Device-UUID':str(dev),'X-Sync-Device-Secret':secret}; gate=Barrier(2)
 def post(p):
  gate.wait(timeout=10); return requests.post(f'http://127.0.0.1:{p}/api/v1/sync/v2/proof-capabilities',json=body,headers=headers,timeout=20)
 with ThreadPoolExecutor(max_workers=2) as pool: rs=list(pool.map(post,ports))
 seq=sorted(r.json()['data']['advertisement_sequence'] for r in rs); print('previous=',previous,'responses=',[(r.status_code,r.json()['data']['status'],r.json()['data']['advertisement_sequence']) for r in rs]); assert seq==[previous+1,previous+2]
 with Session(create_engine(DB)) as db:
  row=db.scalar(select(ProofTransportCapability).where(ProofTransportCapability.peer_device_uuid==dev,ProofTransportCapability.connection_scope==scope)); assert row and row.advertisement_sequence==previous+2 and row.proof_transport_version==1; print('durable=one final_sequence=',row.advertisement_sequence,'version=',row.proof_transport_version)
finally:
 for p in ps:
  if p.poll() is None: p.terminate(); p.wait(timeout=10)
