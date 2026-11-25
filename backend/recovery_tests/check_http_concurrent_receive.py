"""Stage-four concurrent receive of one event under two publisher scopes."""
import os,sys,uuid,time,socket,threading,subprocess
from pathlib import Path
from datetime import datetime,timezone
import requests
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization,SyncEventPublication,SyncTransportEvent,SyncEventInbox,SyncPublicationReceipt,SyncTransportCursor
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
from sqlalchemy.engine import make_url

base=make_url(settings.database_url); dburl=base.set(database='ibn_sina_transport_d'); run=uuid.uuid4().hex[:10]; channel='concurrent-'+run; clinic=uuid.uuid4(); origin=uuid.uuid4(); ogen=uuid.uuid4(); s1=uuid.uuid4(); s2=uuid.uuid4(); gen1=uuid.uuid4(); gen2=uuid.uuid4(); dest=uuid.uuid4(); secret='stage4-concurrent-secret'; event=uuid.uuid4(); revision=uuid.uuid4(); entity=uuid.uuid4(); payload={'concurrent_receive':event.hex}; digest=payload_sha256(payload); procs=[]; port=0
def stop(p):
 if p and p.poll() is None: p.terminate()
def api():
 global port
 s=socket.socket(); s.bind(('127.0.0.1',0)); port=s.getsockname()[1]; s.close(); e={**os.environ,'DATABASE_URL':dburl.render_as_string(hide_password=False)}; p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); procs.append(p); end=time.time()+30
 while time.time()<end:
  if p.poll() is not None: raise RuntimeError('api_exited')
  try:
   with socket.create_connection(('127.0.0.1',port),.2): return p
  except OSError: time.sleep(.1)
 raise RuntimeError('api_not_ready')
def envelope(pub,pgen,seq):
 return {'event_uuid':str(event),'source_clinic_uuid':str(clinic),'source_device_uuid':str(origin),'source_generation_uuid':str(ogen),'source_sequence':11,'entity_type':'medical_visits','entity_uuid':str(entity),'revision_uuid':str(revision),'parent_revision_uuid':None,'operation':'update','schema_version':1,'payload':payload,'content_sha256':digest,'publication_source_device_uuid':str(pub),'publication_source_generation_uuid':str(pgen),'publication_channel':channel,'publish_sequence':seq}
try:
 with create_engine(dburl).connect() as c: assert c.execute(text('select current_database()')).scalar()== 'ibn_sina_transport_d' and c.execute(text('select version_num from alembic_version')).scalar()=='20261008_15'
 h=CentralSyncService()._hash_secret(secret)
 with Session(create_engine(dburl)) as db:
  for d in (origin,s1,s2,dest): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='concurrent-'+d.hex,device_name='concurrent',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
  db.add(SyncRelayAuthorization(carrier_device_uuid=dest,origin_device_uuid=origin,origin_generation_uuid=ogen,destination_device_uuid=dest,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
  db.add(SyncChange(change_uuid=event,revision_uuid=revision,entity_type='medical_visits',entity_uuid=entity,operation='update',entity_version=1,payload=payload,source_clinic_uuid=clinic,source_device_uuid=origin,source_generation_uuid=ogen,source_sequence=11,schema_version=1,content_sha256=digest,occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); db.commit()
  svc=SyncTransportService(); svc.publish_committed(db,channel=channel,source_device_uuid=origin,source_generation_uuid=ogen,source_clinic_uuid=clinic,publisher_device_uuid=s1,publisher_generation_uuid=gen1); svc.publish_committed(db,channel=channel,source_device_uuid=origin,source_generation_uuid=ogen,source_clinic_uuid=clinic,publisher_device_uuid=s2,publisher_generation_uuid=gen2)
  pubs=db.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==event).order_by(SyncEventPublication.publish_sequence)).all(); assert len(pubs)==2; envs=[envelope(pubs[0].publisher_device_uuid,pubs[0].publisher_generation_uuid,pubs[0].publish_sequence),envelope(pubs[1].publisher_device_uuid,pubs[1].publisher_generation_uuid,pubs[1].publish_sequence)]
 p=api(); url=f'http://127.0.0.1:{port}/api/v1/sync/v2/receive'; barrier=threading.Barrier(2); results=[]
 def send(body):
  barrier.wait(timeout=10); r=requests.post(url,json={'contract_version':'2.1','source_clinic_uuid':str(clinic),'source_device_uuid':str(origin),'source_generation_uuid':str(ogen),'publisher_device_uuid':body['publication_source_device_uuid'],'publisher_generation_uuid':body['publication_source_generation_uuid'],'publisher_clinic_uuid':str(clinic),'channel':channel,'events':[body],'limit':1},headers={'X-Sync-Device-UUID':str(dest),'X-Sync-Device-Secret':secret},timeout=20); results.append((r.status_code, r.json().get('detail',{}).get('details',{}).get('code')))
 ts=[threading.Thread(target=send,args=(e,)) for e in envs]; [t.start() for t in ts]; [t.join(30) for t in ts]; print('concurrent_results',results); assert len(results)==2 and all(code!=500 for _,code in results)
 with Session(create_engine(dburl)) as db:
  assert db.scalar(select(func.count()).select_from(SyncTransportEvent).where(SyncTransportEvent.event_uuid==event))==1; assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==event))==1; assert db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==event,SyncPublicationReceipt.channel==channel))==2; print('concurrent_persistent source=1 inbox=1 receipts=2')
 print('PASS concurrent receive scopes; no medical apply')
finally:
 for p in reversed(procs): stop(p)
