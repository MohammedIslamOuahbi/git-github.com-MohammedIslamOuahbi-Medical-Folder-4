import os,sys,subprocess,time,uuid,requests
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventInbox,SyncTransportCursor,SyncEventDelivery
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
B=make_url(settings.database_url); A=B.render_as_string(hide_password=False); D=B.set(database='ibn_sina_transport_d').render_as_string(hide_password=False)
src,peer,gen,clinic=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); secret='stage4-fail-secret'; ch='fail-'+src.hex[:8]; ev=[]
def seed(url):
 with Session(create_engine(url)) as db:
  h=CentralSyncService()._hash_secret(secret)
  for x in (src,peer):
   if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==x)): db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='fail-'+x.hex,device_name='fail',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.commit()
def start(url,port,fail=False):
 e=os.environ.copy();e['DATABASE_URL']=url
 script='recovery_tests/_run_api_receive_fail.py' if fail else '-m'
 args=[sys.executable,script] if fail else [sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)]
 if fail: pass
 else: args += []
 return subprocess.Popen(args,cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ps=[]
try:
 seed(A);seed(D)
 for i in range(3):
  x=uuid.uuid4();ev.append({'event_uuid':str(x),'source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'source_sequence':i+1,'entity_type':'medical_visits','entity_uuid':str(uuid.uuid4()),'revision_uuid':str(uuid.uuid4()),'operation':'update','schema_version':1,'payload':{'synthetic':x.hex},'content_sha256':''})
  ev[-1]['content_sha256']=payload_sha256(ev[-1]['payload'])
 with Session(create_engine(D)) as db:
  before=db.scalar(select(func.count()).select_from(MedicalVisit)); assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_([uuid.UUID(x['event_uuid']) for x in ev])))==0
 ps=[start(A,8871),start(D,8872,True)];time.sleep(4);h={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret};body={'source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'events':ev,'limit':3}
 r=requests.post('http://127.0.0.1:8872/api/v1/sync/v2/receive',json=body,headers=h,timeout=10);assert r.status_code>=500
 with Session(create_engine(D)) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_([uuid.UUID(x['event_uuid']) for x in ev])))==0; assert db.scalar(select(func.count()).select_from(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.channel==ch))==0; assert db.scalar(select(func.count()).select_from(MedicalVisit))==before
 for p in ps:p.terminate()
 for p in ps:
  try:p.wait(timeout=5)
  except: p.kill()
 ps=[start(A,8871),start(D,8872)];time.sleep(4);r=requests.post('http://127.0.0.1:8872/api/v1/sync/v2/receive',json=body,headers=h,timeout=10);assert r.ok and r.json()['data']['accepted']==3
 with Session(create_engine(D)) as db:
  inbox_count=db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_([uuid.UUID(x['event_uuid']) for x in ev]))); med_count=db.scalar(select(func.count()).select_from(MedicalVisit)); print('verification counts',inbox_count,med_count,before); assert inbox_count==3; assert med_count==before
 print('PASS HTTP receive transaction rollback, retry, durable inbox/cursor, medical tables unchanged')
finally:
 for p in ps:
  p.terminate()
  try:p.wait(timeout=5)
  except: p.kill()
