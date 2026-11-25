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
BASE=make_url(settings.database_url);A='ibn_sina_recovery_test';C='ibn_sina_transport_c_4a2d1164';PA=8961;PC=8962
run=uuid.uuid4().hex[:8];event,origin,ogen,clinic,p1,g1,p2,g2,peer=[uuid.uuid4() for _ in range(9)];ch='cross-'+run;secret='cross-'+run;procs=[]
def e(db):return create_engine(BASE.set(database=db),pool_pre_ping=True)
def u(db):return BASE.set(database=db).render_as_string(hide_password=False)
def stop(p):
    if p.poll() is None:p.terminate();p.wait(5)
def start(db,port):return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env={**os.environ,'DATABASE_URL':u(db)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait(port):
    end=time.time()+30
    while time.time()<end:
        try:
            with socket.create_connection(('127.0.0.1',port),.2):return
        except OSError:time.sleep(.2)
    raise TimeoutError('api_not_ready')
try:
    for db in (A,C):
        with e(db).connect() as q:assert q.execute(text('select version_num from alembic_version')).scalar_one()=='20261008_15';assert q.execute(text('select current_database()')).scalar_one()==db
    h=CentralSyncService()._hash_secret(secret); payload={'synthetic_cross_scope':run}
    with Session(e(A)) as s:
        for d in (peer,origin):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='cross-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=origin,origin_generation_uuid=ogen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True))
        for p,g in ((p1,g1),(p2,g2)):
            s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=p,origin_generation_uuid=g,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True))
        s.add(SyncChange(change_uuid=event,revision_uuid=uuid.uuid4(),entity_type='synthetic_transport',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=payload,source_clinic_uuid=clinic,source_device_uuid=origin,source_generation_uuid=ogen,source_sequence=1,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0));s.commit()
        svc=SyncTransportService()
        for p,g in ((p1,g1),(p2,g2)):
            svc.publish_committed(s,channel=ch,source_device_uuid=origin,source_generation_uuid=ogen,source_clinic_uuid=clinic,publisher_device_uuid=p,publisher_generation_uuid=g);svc.queue_for_peer(s,peer_device_uuid=peer,channel=ch,source_clinic_uuid=clinic,source_generation_uuid=ogen,source_device_uuid=origin,limit=10)
    with Session(e(C)) as s:
        for d in (peer,origin):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='cross-c-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=origin,origin_generation_uuid=ogen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));s.commit()
    procs=[start(A,PA),start(C,PC)];wait(PA);wait(PC);H={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret}; tokens={}
    for p,g in ((p1,g1),(p2,g2)):
        pull={'contract_version':'2.1','source_clinic_uuid':str(clinic),'source_device_uuid':str(origin),'source_generation_uuid':str(ogen),'channel':ch,'limit':10,'after_sequence':0,'publisher_device_uuid':str(p),'publisher_generation_uuid':str(g),'publisher_clinic_uuid':str(clinic)}
        r=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);assert r.ok;ev=r.json()['data']['events'][0];tokens[(p,g)]=ev['lease_token'];rr=requests.post(f'http://127.0.0.1:{PC}/api/v1/sync/v2/receive',json={**pull,'events':[ev]},headers=H,timeout=10);assert rr.ok
    def ack(p,g,tok):return requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/ack',json={'contract_version':'2.1','event_uuid':str(event),'channel':ch,'lease_token':tok,'publisher_device_uuid':str(p),'publisher_generation_uuid':str(g),'publisher_clinic_uuid':str(clinic)},headers=H,timeout=10)
    cross1=ack(p1,g1,tokens[(p2,g2)]);cross2=ack(p2,g2,tokens[(p1,g1)]);print('cross_ack_statuses',cross1.status_code,cross2.status_code);assert cross1.status_code in (409,422,403) and cross2.status_code in (409,422,403)
    with Session(e(A)) as s: assert all(d.status!='delivered' for d in s.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==event)).all())
    ok1=ack(p1,g1,tokens[(p1,g1)]);ok2=ack(p2,g2,tokens[(p2,g2)]);print('valid_ack_statuses',ok1.status_code,ok2.status_code);assert ok1.ok and ok2.ok
    print('PASS cross-scope ACK isolation; valid ACKs delivered independently; inbox=1')
finally:
    for p in procs:stop(p)
