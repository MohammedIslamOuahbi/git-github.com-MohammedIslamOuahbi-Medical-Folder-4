import os,sys,uuid,time,socket,subprocess
from pathlib import Path
from datetime import datetime,timezone
import requests
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization,SyncEventDelivery,SyncEventInbox
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
BASE=make_url(settings.database_url);A='ibn_sina_recovery_test';C='ibn_sina_transport_d';PA=8881;PC=8882
run=uuid.uuid4().hex[:8];src,peer,gen,clinic,pub,pgen,eid=[uuid.uuid4() for _ in range(7)];ch='lease-'+run;secret='lease-'+run;procs=[]
def eng(db):return create_engine(BASE.set(database=db),pool_pre_ping=True)
def url(db):return BASE.set(database=db).render_as_string(hide_password=False)
def stop(p):
    if p.poll() is None:p.terminate();p.wait(5)
def start(db,port,short=False):
    env={**os.environ,'DATABASE_URL':url(db)};args=[sys.executable,'recovery_tests/_run_api_short_lease.py'] if short else [sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)]
    return subprocess.Popen(args,cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait(port):
    end=time.time()+30
    while time.time()<end:
        try:
            with socket.create_connection(('127.0.0.1',port),.2):return
        except OSError:time.sleep(.2)
    raise TimeoutError('api_not_ready')
try:
    for db in (A,C):
        with eng(db).connect() as q:ident=q.execute(text('select current_database(),current_schema()')).one();head=q.execute(text('select version_num from alembic_version')).scalar_one();print('identity',ident[0],ident[1],'head',head);assert ident[0]==db and head=='20261008_15'
    h=CentralSyncService()._hash_secret(secret);payload={'synthetic_lease':run}
    with Session(eng(A)) as s:
        for d in (src,peer):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='lease-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True))
        s.add(SyncChange(change_uuid=eid,revision_uuid=uuid.uuid4(),entity_type='synthetic_transport',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=1,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0));s.commit();svc=SyncTransportService();svc.publish_committed(s,channel=ch,source_device_uuid=src,source_generation_uuid=gen,source_clinic_uuid=clinic,publisher_device_uuid=pub,publisher_generation_uuid=pgen);svc.queue_for_peer(s,peer_device_uuid=peer,channel=ch,source_clinic_uuid=clinic,source_generation_uuid=gen,source_device_uuid=src,limit=10)
    with Session(eng(C)) as s:
        for d in (peer,src):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='lease-c-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));s.commit()
    procs=[start(A,PA,True),start(C,PC)];wait(PA);wait(PC);H={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret};pull={'contract_version':'2.1','source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'limit':1,'after_sequence':0,'publisher_device_uuid':str(pub),'publisher_generation_uuid':str(pgen),'publisher_clinic_uuid':str(clinic)}
    r=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);assert r.ok;ev1=r.json()['data']['events'][0];t1=ev1['lease_token'];time.sleep(6)
    r=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);assert r.ok;ev2=r.json()['data']['events'][0];t2=ev2['lease_token'];assert t1!=t2 and ev1['event_uuid']==ev2['event_uuid'] and ev1['content_sha256']==ev2['content_sha256']
    def ack(tok):return requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/ack',json={'contract_version':'2.1','event_uuid':str(eid),'channel':ch,'lease_token':tok,'publisher_device_uuid':str(pub),'publisher_generation_uuid':str(pgen),'publisher_clinic_uuid':str(clinic)},headers=H,timeout=10)
    old=ack(t1);print('old_token_before_receive',old.status_code);assert old.status_code==409
    rr=requests.post(f'http://127.0.0.1:{PC}/api/v1/sync/v2/receive',json={**pull,'events':[ev2]},headers=H,timeout=10);assert rr.ok;good=ack(t2);print('new_token_ack',good.status_code);assert good.ok;assert ack(t2).ok;assert ack(t1).status_code==409
    with Session(eng(A)) as s:d=s.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==eid,SyncEventDelivery.publisher_device_uuid==pub,SyncEventDelivery.publisher_generation_uuid==pgen));print('delivery_status',d.status);assert d.status=='delivered'
    with Session(eng(C)) as s:assert s.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==eid))==1
    print('PASS lease expiry, new token fencing, stale token rejection, idempotent ACK, durable inbox')
finally:
    for p in procs:stop(p)
