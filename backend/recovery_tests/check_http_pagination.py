import os,sys,uuid,subprocess,time,requests
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncEventDelivery
from app.models.medical_visit import MedicalVisit
from app.services.sync_journal import payload_sha256
from app.services.central_sync_service import CentralSyncService
B=make_url(settings.database_url); A=B.render_as_string(hide_password=False); D=B.set(database='ibn_sina_transport_d').render_as_string(hide_password=False)
src,peer,gen,clinic=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); secret='stage4-page-secret'; ch='page-'+src.hex[:8]; ids=[]
def seed(url):
 from app.models.sync_device import SyncDevice
 with Session(create_engine(url)) as db:
  h=CentralSyncService()._hash_secret(secret)
  for x in (src,peer):
   if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==x)): db.add(SyncDevice(uuid=x,installation_uuid=uuid.uuid4(),device_code='page-'+x.hex,device_name='page',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.commit()
def start(url,p):
 e=os.environ.copy();e['DATABASE_URL']=url
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ps=[]
try:
 seed(A);seed(D)
 with Session(create_engine(A)) as db:
  before=db.scalar(select(func.count()).select_from(MedicalVisit))
  for i in range(7):
   x=uuid.uuid4();ids.append(x);p={'synthetic_page_id':x.hex};db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=i+1,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
  db.commit()
 ps=[start(A,8861),start(D,8862)];time.sleep(4); h={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret}; seen=[]; cursor=0
 for page in range(4):
  if page==1:
   for p in ps: p.terminate()
   for p in ps:
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill()
   ps=[start(A,8861),start(D,8862)];time.sleep(4)
   durable=requests.post('http://127.0.0.1:8862/api/v1/sync/v2/cursor',json={'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch},headers=h,timeout=10).json()['data']; cursor=durable['last_source_sequence']
  pull={'source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'limit':2,'after_sequence':cursor}
  r=requests.post('http://127.0.0.1:8861/api/v1/sync/v2/pull',json=pull,headers=h,timeout=10);r.raise_for_status(); data=r.json()['data']; ev=data['events']
  if not ev: break
  receive={'source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'events':ev,'limit':2}
  rr=requests.post('http://127.0.0.1:8862/api/v1/sync/v2/receive',json=receive,headers=h,timeout=10);rr.raise_for_status(); assert rr.json()['data']['accepted']==len(ev)
  for e in ev:
   requests.post('http://127.0.0.1:8861/api/v1/sync/v2/ack',json={'event_uuid':e['event_uuid'],'channel':ch,'lease_token':e['lease_token']},headers=h,timeout=10).raise_for_status()
   seen.append(uuid.UUID(e['event_uuid']))
  cursor+=len(ev)
 assert set(seen)==set(ids) and len(seen)==7
 with Session(create_engine(D)) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==7 and db.scalar(select(func.count()).select_from(MedicalVisit))==0
 with Session(create_engine(A)) as db:
  assert db.scalar(select(func.count()).select_from(MedicalVisit))==before
  bad={'event_uuid':str(ids[0]),'channel':ch,'lease_token':str(uuid.uuid4())}
  # wrong token must reject even after delivered is checked by a separate HTTP request
  x=requests.post('http://127.0.0.1:8861/api/v1/sync/v2/ack',json=bad,headers=h,timeout=10);assert x.status_code==409
 print('PASS HTTP pagination/resume synthetic 7 events, one delivery each, medical tables unchanged; bad delivered ACK rejected')
finally:
 for p in ps:
  p.terminate()
 for p in ps:
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill()
