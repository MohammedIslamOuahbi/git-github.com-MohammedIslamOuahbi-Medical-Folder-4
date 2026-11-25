import os,sys,uuid,subprocess,time,requests
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization,SyncEventInbox,SyncTransportEvent,SyncPublicationReceipt,SyncTransportCursor,SyncEventDelivery
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
B=make_url(settings.database_url); A=B.render_as_string(hide_password=False); D=B.set(database='ibn_sina_transport_d').render_as_string(hide_password=False)
P,Q,genP,genQ,clP,clQ=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); secretP='p-secret'; secretQ='q-secret'; chP='p-'+P.hex[:8]; chQ='q-'+Q.hex[:8]; procs=[]
def migrate(url):
 e=os.environ.copy();e['DATABASE_URL']=url; r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60); assert r.returncode==0
def seed(url):
 with Session(create_engine(url)) as db:
  for d,sec in ((P,secretP),(Q,secretQ)):
   if not db.scalar(select(SyncDevice).where(SyncDevice.uuid==d)):
    db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='iso-'+d.hex,device_name='iso',registered_at=datetime.now(timezone.utc),central_secret_hash=CentralSyncService()._hash_secret(sec),is_active=True))
  for carrier,origin,g,dst,ch,cl in ((P,P,genP,P,chP,clP),(Q,Q,genQ,Q,chQ,clQ)):
   if not db.scalar(select(SyncRelayAuthorization.id).where(SyncRelayAuthorization.carrier_device_uuid==carrier,SyncRelayAuthorization.origin_device_uuid==origin,SyncRelayAuthorization.origin_generation_uuid==g,SyncRelayAuthorization.destination_device_uuid==dst,SyncRelayAuthorization.channel==ch)):
    db.add(SyncRelayAuthorization(carrier_device_uuid=carrier,origin_device_uuid=origin,origin_generation_uuid=g,destination_device_uuid=dst,channel=ch,created_at=datetime.now(timezone.utc),is_active=True))
  db.commit()
def api(url,port):
 e=os.environ.copy();e['DATABASE_URL']=url;return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def ready(p,port):
 end=time.time()+20
 while time.time()<end:
  if p.poll() is not None: raise RuntimeError(f'api {port} exited {p.returncode}')
  try:
   if requests.get(f'http://127.0.0.1:{port}/openapi.json',timeout=1).status_code==200:return
  except requests.RequestException: pass
  time.sleep(.2)
 raise RuntimeError(f'api {port} timeout')
def snap(url):
 with Session(create_engine(url)) as db:return tuple(db.scalar(select(func.count()).select_from(t)) for t in (SyncEventInbox,SyncTransportEvent,SyncPublicationReceipt,SyncTransportCursor,SyncEventDelivery,MedicalVisit))
try:
 migrate(A);migrate(D);seed(A);seed(D)
 with Session(create_engine(A)) as db:
  for src,g,cl,eid,ch,seq in ((P,genP,clP,uuid.uuid4(),chP,11),(Q,genQ,clQ,uuid.uuid4(),chQ,22)):
   pay={'scope':eid.hex};db.add(SyncChange(change_uuid=eid,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=pay,source_clinic_uuid=cl,source_device_uuid=src,source_generation_uuid=g,source_sequence=seq,schema_version=1,content_sha256=payload_sha256(pay),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
  db.commit()
 procs=[api(A,8831),api(D,8832)];ready(procs[0],8831);ready(procs[1],8832)
 def pull(dev,sec,cl,src,g,ch):
  body={'contract_version':'2.1','source_clinic_uuid':str(cl),'source_device_uuid':str(src),'source_generation_uuid':str(g),'channel':ch,'limit':10,'after_sequence':0,'publisher_device_uuid':str(src),'publisher_generation_uuid':str(g),'publisher_clinic_uuid':str(cl)}
  return requests.post('http://127.0.0.1:8831/api/v1/sync/v2/pull',json=body,headers={'X-Sync-Device-UUID':str(dev),'X-Sync-Device-Secret':sec},timeout=10)
 pgood=pull(P,secretP,clP,P,genP,chP); qgood=pull(Q,secretQ,clQ,Q,genQ,chQ); qbad=pull(Q,secretQ,clP,P,genP,chP)
 events_p=pgood.json().get('data',{}).get('events',[])
 ack_status=None
 if events_p:
  e=events_p[0]; ack_body={'contract_version':'2.1','event_uuid':e['event_uuid'],'channel':chP,'lease_token':e['lease_token'],'publisher_device_uuid':str(P),'publisher_generation_uuid':str(genP),'publisher_clinic_uuid':str(clP)}
  ack_status=requests.post('http://127.0.0.1:8831/api/v1/sync/v2/ack',json=ack_body,headers={'X-Sync-Device-UUID':str(Q),'X-Sync-Device-Secret':secretQ},timeout=10).status_code
 print('P pull',pgood.status_code,'Q own pull',qgood.status_code,'Q foreign pull',qbad.status_code)
 before=snap(D); foreign={'contract_version':'2.1','source_clinic_uuid':str(clP),'source_device_uuid':str(P),'source_generation_uuid':str(genP),'channel':chP,'events':[],'limit':10,'publisher_device_uuid':str(P),'publisher_generation_uuid':str(genP),'publisher_clinic_uuid':str(clP)}
 qrecv=requests.post('http://127.0.0.1:8832/api/v1/sync/v2/receive',json=foreign,headers={'X-Sync-Device-UUID':str(Q),'X-Sync-Device-Secret':secretQ},timeout=10)
 qcur=requests.post('http://127.0.0.1:8832/api/v1/sync/v2/cursor',json={'contract_version':'2.1','source_device_uuid':str(P),'source_generation_uuid':str(genP),'channel':chP,'publisher_device_uuid':str(P),'publisher_generation_uuid':str(genP),'publisher_clinic_uuid':str(clP)},headers={'X-Sync-Device-UUID':str(Q),'X-Sync-Device-Secret':secretQ},timeout=10)
 after=snap(D); print('Q foreign receive',qrecv.status_code,'Q foreign cursor',qcur.status_code,'Q foreign ack',ack_status,'snapshot_unchanged',before==after); assert qbad.status_code!=500 and qrecv.status_code!=500 and qcur.status_code!=500
 print('PASS peer isolation checks; no medical rows changed')
finally:
 for p in procs:
  if p.poll() is None:p.terminate()
 for p in procs:
  try:p.wait(5)
  except: p.kill()

