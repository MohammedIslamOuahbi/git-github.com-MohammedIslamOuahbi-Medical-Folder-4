"""Stage-four concurrent receive: reversed E1/E2 batches acquire locks safely."""
import os, sys, uuid, time, socket, threading, subprocess
from pathlib import Path
from datetime import datetime, timezone
import requests
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncRelayAuthorization, SyncEventPublication, SyncTransportEvent, SyncEventInbox, SyncPublicationReceipt, SyncTransportCursor
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
from sqlalchemy.engine import make_url

base = make_url(settings.database_url); dburl = base.set(database='ibn_sina_transport_d')
run = uuid.uuid4().hex[:10]; channel = 'ordered-' + run; clinic = uuid.uuid4(); origin = uuid.uuid4(); ogen = uuid.uuid4(); dest = uuid.uuid4()
s1, s2, g1, g2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(); secret = 'stage4-ordered-secret'; procs=[]; port=0
events = [uuid.uuid4(), uuid.uuid4()]; revisions=[uuid.uuid4(),uuid.uuid4()]; entities=[uuid.uuid4(),uuid.uuid4()]
def stop(p):
    if p and p.poll() is None: p.terminate()
def start_api():
    global port
    sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
    env={**os.environ,'DATABASE_URL':dburl.render_as_string(hide_password=False)}
    p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); procs.append(p)
    end=time.time()+30
    while time.time()<end:
        if p.poll() is not None: raise RuntimeError('api_exited')
        try:
            with socket.create_connection(('127.0.0.1',port),.2): return
        except OSError: time.sleep(.1)
    raise RuntimeError('api_not_ready')
def env_for(pub, gen, event, seq):
    payload={'ordered_receive':event.hex}; digest=payload_sha256(payload)
    return {'event_uuid':str(event),'source_clinic_uuid':str(clinic),'source_device_uuid':str(origin),'source_generation_uuid':str(ogen),'source_sequence':seq+10,'entity_type':'medical_visits','entity_uuid':str(entities[seq-1]),'revision_uuid':str(revisions[seq-1]),'parent_revision_uuid':None,'operation':'update','schema_version':1,'payload':payload,'content_sha256':digest,'publication_source_device_uuid':str(pub),'publication_source_generation_uuid':str(gen),'publication_channel':channel,'publish_sequence':seq}
try:
    with create_engine(dburl).connect() as c:
        assert c.execute(text('select current_database()')).scalar()=='ibn_sina_transport_d'; assert c.execute(text('select version_num from alembic_version')).scalar()=='20261008_15'
    h=CentralSyncService()._hash_secret(secret)
    with Session(create_engine(dburl)) as db:
        for d in (origin,dest): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='ordered-'+d.hex,device_name='ordered',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        for p in (s1,s2): db.add(SyncDevice(uuid=p,installation_uuid=uuid.uuid4(),device_code='ordered-'+p.hex,device_name='ordered',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        db.add(SyncRelayAuthorization(carrier_device_uuid=dest,origin_device_uuid=origin,origin_generation_uuid=ogen,destination_device_uuid=dest,channel=channel,created_at=datetime.now(timezone.utc),is_active=True))
        for i,e in enumerate(events):
            payload={'ordered_receive':e.hex}; db.add(SyncChange(change_uuid=e,revision_uuid=revisions[i],entity_type='medical_visits',entity_uuid=entities[i],operation='update',entity_version=1,payload=payload,source_clinic_uuid=clinic,source_device_uuid=origin,source_generation_uuid=ogen,source_sequence=11+i,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
        db.commit(); svc=SyncTransportService()
        svc.publish_committed(db,channel=channel,source_device_uuid=origin,source_generation_uuid=ogen,source_clinic_uuid=clinic,publisher_device_uuid=s1,publisher_generation_uuid=g1)
        svc.publish_committed(db,channel=channel,source_device_uuid=origin,source_generation_uuid=ogen,source_clinic_uuid=clinic,publisher_device_uuid=s2,publisher_generation_uuid=g2)
        pubs=db.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid.in_(events),SyncEventPublication.publisher_device_uuid==s1).order_by(SyncEventPublication.publish_sequence)).all(); assert len(pubs)==2
        b1=[env_for(s1,g1,events[0],pubs[0].publish_sequence),env_for(s1,g1,events[1],pubs[1].publish_sequence)]
        pubs2=db.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid.in_(events),SyncEventPublication.publisher_device_uuid==s2).order_by(SyncEventPublication.publish_sequence)).all(); assert len(pubs2)==2
        b2=[env_for(s2,g2,events[1],pubs2[1].publish_sequence),env_for(s2,g2,events[0],pubs2[0].publish_sequence)]
    start_api(); url=f'http://127.0.0.1:{port}/api/v1/sync/v2/receive'; barrier=threading.Barrier(2); results=[]
    def send(batch):
        barrier.wait(timeout=10); r=requests.post(url,json={'contract_version':'2.1','source_clinic_uuid':str(clinic),'source_device_uuid':str(origin),'source_generation_uuid':str(ogen),'publisher_device_uuid':batch[0]['publication_source_device_uuid'],'publisher_generation_uuid':batch[0]['publication_source_generation_uuid'],'publisher_clinic_uuid':str(clinic),'channel':channel,'events':batch,'limit':2},headers={'X-Sync-Device-UUID':str(dest),'X-Sync-Device-Secret':secret},timeout=20); results.append((r.status_code, r.json().get('detail',{}).get('details',{}).get('code')))
    ts=[threading.Thread(target=send,args=(b,)) for b in (b1,b2)]; [t.start() for t in ts]; [t.join(30) for t in ts]; print('ordered_results',results); assert len(results)==2 and all(code!=500 for _,code in results) and all(status==200 for status,_ in results)
    with Session(create_engine(dburl)) as db:
        assert db.scalar(select(func.count()).select_from(SyncTransportEvent).where(SyncTransportEvent.event_uuid.in_(events)))==2
        assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(events)))==2
        assert db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid.in_(events),SyncPublicationReceipt.channel==channel))==4
        assert db.scalar(select(func.count()).select_from(SyncTransportCursor).where(SyncTransportCursor.channel==channel))==2
    print('PASS ordered concurrent receive: backend_overlap=2 batches reversed, source=2 inbox=2 receipts=4 cursors=2')
finally:
    for p in reversed(procs): stop(p)
