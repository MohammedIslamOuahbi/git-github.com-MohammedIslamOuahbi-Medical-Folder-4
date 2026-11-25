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
from app.models.sync_transport import SyncRelayAuthorization,SyncTransportCursor,SyncEventInbox,SyncPublicationReceipt
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
BASE=make_url(settings.database_url);A='ibn_sina_recovery_test';B='ibn_sina_transport_d';PA=8871;PB=8872
run=uuid.uuid4().hex[:8];src,peer,gen,clinic,pub,pgen=[uuid.uuid4() for _ in range(6)];ch='gap-'+run;secret='gap-'+run;ids=[];procs=[]
def eng(db):return create_engine(BASE.set(database=db),pool_pre_ping=True)
def url(db):return BASE.set(database=db).render_as_string(hide_password=False)
def stop(p):
    if p.poll() is None:p.terminate();p.wait(5)
def start(db,port):return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env={**os.environ,'DATABASE_URL':url(db)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait(port):
    end=time.time()+30
    while time.time()<end:
        try:
            with socket.create_connection(('127.0.0.1',port),.2):return
        except OSError:time.sleep(.2)
    raise TimeoutError('api_not_ready')
try:
    for db in (A,B):
        with eng(db).connect() as q:ident=q.execute(text('select current_database(),current_schema()')).one();head=q.execute(text('select version_num from alembic_version')).scalar_one();print('identity',ident[0],ident[1],'head',head);assert ident[0]==db and head=='20261008_15'
    h=CentralSyncService()._hash_secret(secret)
    with Session(eng(A)) as s:
        for d in (src,peer):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='gap-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True))
        for seq in (10,30,90,140):
            eid=uuid.uuid4();ids.append(eid);p={'synthetic_gap':eid.hex};s.add(SyncChange(change_uuid=eid,revision_uuid=uuid.uuid4(),entity_type='synthetic_transport',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=seq,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
        s.commit()
    with Session(eng(B)) as s:
        for d in (src,peer):s.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='gap-b-'+d.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));s.commit()
    with Session(eng(A)) as s:
        from app.services.sync_transport_service import SyncTransportService
        svc=SyncTransportService();svc.publish_committed(s,channel=ch,source_device_uuid=src,source_generation_uuid=gen,source_clinic_uuid=clinic,publisher_device_uuid=pub,publisher_generation_uuid=pgen);svc.queue_for_peer(s,peer_device_uuid=peer,channel=ch,source_clinic_uuid=clinic,source_generation_uuid=gen,source_device_uuid=src,limit=10)
    procs=[start(A,PA),start(B,PB)];wait(PA);wait(PB);H={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret};pull={'contract_version':'2.1','source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'limit':2,'after_sequence':0,'publisher_device_uuid':str(pub),'publisher_generation_uuid':str(pgen),'publisher_clinic_uuid':str(clinic)}
    p1=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);assert p1.ok;page1=p1.json()['data'];p2=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);assert p2.ok;page2=p2.json()['data'];assert len(page1['events'])==2 and len(page2['events'])==2 and max(e['publish_sequence'] for e in page1['events'])<min(e['publish_sequence'] for e in page2['events'])
    def receive(page):
        r=requests.post(f'http://127.0.0.1:{PB}/api/v1/sync/v2/receive',json={**pull,'events':page['events']},headers=H,timeout=10);assert r.ok;return r.json()['data']
    receive(page2)
    with Session(eng(B)) as s:cur=s.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.publisher_device_uuid==pub,SyncTransportCursor.publisher_generation_uuid==pgen,SyncTransportCursor.channel==ch));print('cursor_after_newer',cur.last_publish_sequence,cur.last_publication_event_uuid);assert cur.last_publish_sequence==0 and cur.last_publication_event_uuid is None
    for p in procs:stop(p)
    procs=[start(A,PA),start(B,PB)];wait(PA);wait(PB)
    curresp=requests.post(f'http://127.0.0.1:{PB}/api/v1/sync/v2/cursor',json={'contract_version':'2.1','source_device_uuid':str(src),'source_generation_uuid':str(gen),'channel':ch,'publisher_device_uuid':str(pub),'publisher_generation_uuid':str(pgen),'publisher_clinic_uuid':str(clinic)},headers=H,timeout=10);assert curresp.ok;assert curresp.json()['data']['last_publish_sequence']==0
    receive(page1)
    for page in (page1,page2):
        for e in page['events']:
            ack={'contract_version':'2.1','event_uuid':e['event_uuid'],'channel':ch,'lease_token':e['lease_token'],'publisher_device_uuid':str(pub),'publisher_generation_uuid':str(pgen),'publisher_clinic_uuid':str(clinic)};assert requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/ack',json=ack,headers=H,timeout=10).ok
    with Session(eng(B)) as s:cur=s.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.publisher_device_uuid==pub,SyncTransportCursor.publisher_generation_uuid==pgen,SyncTransportCursor.channel==ch));print('cursor_after_gap',cur.last_publish_sequence,cur.last_publication_event_uuid);assert cur.last_publish_sequence==4;assert s.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==4
    receive(page2);receive(page1)
    print('PASS publication gap: newer first held cursor, restart restored gap, older completed coverage, replays idempotent')
finally:
    for p in procs:stop(p)
