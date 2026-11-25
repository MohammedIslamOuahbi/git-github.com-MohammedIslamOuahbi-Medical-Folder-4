import os, sys, uuid, time, socket, subprocess, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox, SyncEventDelivery, SyncEventPublication, SyncPublicationReceipt, SyncTransportCursor, SyncRelayAuthorization
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService

BASE = make_url(settings.database_url)
DB = {'B':'ibn_sina_transport_d','D':'ibn_sina_recovery_test','C':'ibn_sina_transport_c_4a2d1164'}
PORT = {'B':8981,'D':8982,'C':8983}; RUN=uuid.uuid4().hex[:8]; CHANNEL='http-redelivery-'+RUN
ORIGIN,GEN,CLINIC,EVENT,ENTITY=[uuid.uuid4() for _ in range(5)]; PEER=uuid.uuid4(); PUBLISHER={'B':uuid.uuid4(),'D':uuid.uuid4()}; PUBGEN={'B':uuid.uuid4(),'D':uuid.uuid4()}; SECRET='stage4-'+RUN; PROCS=[]
def engine(k): return create_engine(BASE.set(database=DB[k]), pool_pre_ping=True)
def dburl(k): return BASE.set(database=DB[k]).render_as_string(hide_password=False)
def stop(p):
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(5)
        except Exception: p.kill()
def start_api(k):
    env={**os.environ,'DATABASE_URL':dburl(k)}; log=Path(tempfile.gettempdir())/f'http-redelivery-{RUN}-{k}.log'; marker=Path(tempfile.gettempdir())/f'http-redelivery-{RUN}-{k}-app.txt'
    code="from app.config import settings; from sqlalchemy import create_engine,text; c=create_engine(settings.database_url).connect(); open(r'"+str(marker)+"','w').write(str((settings.database_name,c.execute(text('select current_database(),current_schema()')).one()))); c.close(); import uvicorn; uvicorn.run('app.main:app',host='127.0.0.1',port="+str(PORT[k])+")"
    p=subprocess.Popen([sys.executable,'-c',code],cwd=str(ROOT),env=env,stdout=log.open('w'),stderr=subprocess.STDOUT); p._marker=str(marker); return p
def wait_api(k):
    end=time.time()+30
    while time.time()<end:
        try:
            with socket.create_connection(('127.0.0.1',PORT[k]),.3): return
        except OSError: time.sleep(.2)
    raise TimeoutError('api_not_ready_'+k)
def start_worker(k, publisher_generation=None):
    publisher_generation = publisher_generation or PUBGEN[k]
    env={**os.environ,'DATABASE_URL':dburl(k),'WORKER_PEER':str(PEER),'WORKER_CARRIER':str(PUBLISHER[k]),'WORKER_PUBLISHER_DEVICE':str(PUBLISHER[k]),'WORKER_PUBLISHER_GENERATION':str(publisher_generation),'WORKER_PUBLISHER_CLINIC':str(CLINIC),'WORKER_CHANNEL':CHANNEL,'WORKER_TARGET':f'http://127.0.0.1:{PORT["C"]}','WORKER_SOURCE':f'http://127.0.0.1:{PORT[k]}','WORKER_SECRET':SECRET,'WORKER_ID':'redelivery-'+k,'WORKER_BATCH_SIZE':'1','WORKER_CYCLES':'4'}
    worker_python = shutil.which('python') or sys.executable
    status=Path(tempfile.gettempdir())/f'http-redelivery-{RUN}-{k}-status.jsonl'; status.unlink(missing_ok=True); env['WORKER_STATUS_FILE']=str(status)
    p=subprocess.Popen([worker_python,'recovery_tests/_run_http_worker.py'],cwd=str(ROOT),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); p._status=str(status); PROCS.append(p); return p
try:
    for k in DB:
        with engine(k).connect() as c:
            ident=c.execute(text('select current_database(),current_schema(),inet_server_port()')).one(); head=c.execute(text('select version_num from alembic_version')).scalar_one(); print('identity',k,ident[0],ident[1],ident[2],'head',head); assert ident[0]==DB[k] and head=='20261008_15'
    h=CentralSyncService()._hash_secret(SECRET); payload={'synthetic_http_redelivery':RUN}
    for k in DB:
        with Session(engine(k)) as s:
            if s.scalar(select(SyncDevice).where(SyncDevice.uuid==PEER)) is None: s.add(SyncDevice(uuid=PEER,installation_uuid=uuid.uuid4(),device_code='peer-'+RUN,device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
            if k == 'C' and s.scalar(select(SyncDevice).where(SyncDevice.uuid==ORIGIN)) is None: s.add(SyncDevice(uuid=ORIGIN,installation_uuid=uuid.uuid4(),device_code='origin-'+RUN,device_name='synthetic-origin',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
            if k in ('B','D'):
                s.add(SyncRelayAuthorization(carrier_device_uuid=PUBLISHER[k],origin_device_uuid=ORIGIN,origin_generation_uuid=GEN,destination_device_uuid=PEER,channel=CHANNEL,created_at=datetime.now(timezone.utc),is_active=True))
                s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=PUBLISHER[k],origin_generation_uuid=PUBGEN[k],destination_device_uuid=PEER,channel=CHANNEL,created_at=datetime.now(timezone.utc),is_active=True))
                s.add(SyncChange(change_uuid=EVENT,revision_uuid=uuid.uuid4(),entity_type='synthetic_transport',entity_uuid=ENTITY,operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=ORIGIN,source_generation_uuid=GEN,source_sequence=9001,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); s.commit()
                svc=SyncTransportService(); svc.publish_committed(s,channel=CHANNEL,source_device_uuid=ORIGIN,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=PUBLISHER[k],publisher_generation_uuid=PUBGEN[k]); svc.queue_for_peer(s,peer_device_uuid=PEER,channel=CHANNEL,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=ORIGIN,limit=10)
            else:
                s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=ORIGIN,origin_generation_uuid=GEN,destination_device_uuid=PEER,channel=CHANNEL,created_at=datetime.now(timezone.utc),is_active=True))
                s.commit()
    with engine('C').connect() as c:
        print('C_fixture_device_count=', c.execute(text('select count(*) from sync_devices where uuid=:u'), {'u': str(PEER)}).scalar())
    for k in DB:
        p=start_api(k); PROCS.append(p); print('api_started',k,'pid',p.pid); wait_api(k); print('api_process_identity',k,Path(p._marker).read_text() if Path(p._marker).exists() else 'missing')
    for k in ('B','D'):
        with Session(engine(k)) as s:
            ev=s.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.change_uuid==EVENT))
            pub=s.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==EVENT)).all()
            dels=s.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT,SyncEventDelivery.peer_device_uuid==PEER,SyncEventDelivery.channel==CHANNEL)).all()
            print('preflight',k,'event=',ev,'publications=',[(str(x.publisher_device_uuid),str(x.publisher_generation_uuid),x.publish_sequence) for x in pub],'deliveries=',[(x.status,x.attempt_count,str(x.publisher_device_uuid),str(x.publisher_generation_uuid),str(x.clinic_uuid)) for x in dels])
            assert ev==1 and pub and dels
        p=start_worker(k); rc=p.wait(45); out=p.stdout.read()[-2000:]; err=p.stderr.read()[-3000:]; status=Path(p._status).read_text(errors='replace') if Path(p._status).exists() else ''
        print('worker',k,'python=',p.args[0],'exit',rc,'stdout=',out,'stderr=',err,'status=',status)
        with Session(engine(k)) as s:
            d=s.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT,SyncEventDelivery.peer_device_uuid==PEER,SyncEventDelivery.channel==CHANNEL)); print('post_worker',k,d.status if d else None,d.last_error_code if d else None,d.attempt_count if d else None)
        assert rc==0
    with Session(engine('C')) as s: inbox=s.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EVENT)); print('C_inbox=',inbox); assert inbox==1
    for k in ('B','D'):
        with Session(engine(k)) as s:
            d=s.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT,SyncEventDelivery.peer_device_uuid==PEER,SyncEventDelivery.channel==CHANNEL)); print('delivery',k,d.status if d else None); assert d and d.status=='delivered'
    with Session(engine('C')) as s:
        for k in ('B','D'):
            receipts=s.scalars(select(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==EVENT,SyncPublicationReceipt.peer_device_uuid==PEER,SyncPublicationReceipt.channel==CHANNEL)).all()
            r=next((x for x in receipts if x.publisher_device_uuid==PUBLISHER[k]),None)
            allc=s.scalars(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==PEER,SyncTransportCursor.source_device_uuid==ORIGIN,SyncTransportCursor.source_generation_uuid==GEN,SyncTransportCursor.channel==CHANNEL)).all()
            c=next((x for x in allc if x.publisher_device_uuid==PUBLISHER[k] and x.publisher_generation_uuid==r.publisher_generation_uuid),None) if r else None
            print('scope',k,'publisher=',PUBLISHER[k],'generation=',r.publisher_generation_uuid if r else None,'publish_sequence=',r.publish_sequence if r else None,'receipt=',bool(r),'all_receipts',[(str(x.publisher_device_uuid),str(x.publisher_generation_uuid),x.publish_sequence) for x in receipts],'cursor=',(c.last_publish_sequence if c else None),str(c.last_publication_event_uuid) if c else None,'all_cursor_scopes',[(str(x.publisher_device_uuid),str(x.publisher_generation_uuid),x.last_publish_sequence) for x in allc])
            assert r and c and c.last_publication_event_uuid==EVENT
    # New publisher generation on B: same event identity, new publication scope.
    new_gen=uuid.uuid4()
    with Session(engine('B')) as s:
        s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=PUBLISHER['B'],origin_generation_uuid=new_gen,destination_device_uuid=PEER,channel=CHANNEL,created_at=datetime.now(timezone.utc),is_active=True))
        svc=SyncTransportService(); svc.publish_committed(s,channel=CHANNEL,source_device_uuid=ORIGIN,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=PUBLISHER['B'],publisher_generation_uuid=new_gen); svc.queue_for_peer(s,peer_device_uuid=PEER,channel=CHANNEL,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=ORIGIN,limit=10)
    p=start_worker('B', new_gen); rc=p.wait(45); print('worker B new_generation exit',rc,'stderr',p.stderr.read()[-1200:]); assert rc==0
    # A later event in the new publisher generation.
    later=uuid.uuid4(); later_payload={'synthetic_http_redelivery_later':RUN}
    with Session(engine('B')) as s:
        s.add(SyncChange(change_uuid=later,revision_uuid=uuid.uuid4(),entity_type='synthetic_transport',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=later_payload,source_clinic_uuid=CLINIC,source_device_uuid=ORIGIN,source_generation_uuid=GEN,source_sequence=9002,schema_version=1,content_sha256=payload_sha256(later_payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); s.commit(); svc=SyncTransportService(); svc.publish_committed(s,channel=CHANNEL,source_device_uuid=ORIGIN,source_generation_uuid=GEN,source_clinic_uuid=CLINIC,publisher_device_uuid=PUBLISHER['B'],publisher_generation_uuid=new_gen); svc.queue_for_peer(s,peer_device_uuid=PEER,channel=CHANNEL,source_clinic_uuid=CLINIC,source_generation_uuid=GEN,source_device_uuid=ORIGIN,limit=10)
    p=start_worker('B', new_gen); rc=p.wait(45); print('worker B later exit',rc,'stderr',p.stderr.read()[-1200:]); assert rc==0
    with Session(engine('B')) as s:
        new_deliveries=s.scalars(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid.in_([EVENT,later]),SyncEventDelivery.peer_device_uuid==PEER,SyncEventDelivery.channel==CHANNEL,SyncEventDelivery.publisher_device_uuid==PUBLISHER['B'],SyncEventDelivery.publisher_generation_uuid==new_gen,SyncEventDelivery.clinic_uuid==CLINIC)).all()
        print('new_generation_source_deliveries=',[(str(d.event_uuid),d.status) for d in new_deliveries])
        assert len(new_deliveries)==2 and all(d.status=='delivered' for d in new_deliveries)
    with Session(engine('C')) as s:
        old_cursor=s.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==PEER,SyncTransportCursor.source_device_uuid==ORIGIN,SyncTransportCursor.source_generation_uuid==GEN,SyncTransportCursor.publisher_device_uuid==PUBLISHER['B'],SyncTransportCursor.publisher_generation_uuid==PUBGEN['B'],SyncTransportCursor.channel==CHANNEL))
        ni=s.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==later)); nr=s.scalars(select(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid.in_([EVENT,later]),SyncPublicationReceipt.peer_device_uuid==PEER,SyncPublicationReceipt.publisher_device_uuid==PUBLISHER['B'],SyncPublicationReceipt.publisher_generation_uuid==new_gen,SyncPublicationReceipt.channel==CHANNEL)).all(); nc=s.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==PEER,SyncTransportCursor.source_device_uuid==ORIGIN,SyncTransportCursor.source_generation_uuid==GEN,SyncTransportCursor.publisher_device_uuid==PUBLISHER['B'],SyncTransportCursor.publisher_generation_uuid==new_gen,SyncTransportCursor.channel==CHANNEL)); print('new_generation_inbox_later=',ni,'receipts=',len(nr),'cursor=',(nc.last_publish_sequence if nc else None),str(nc.last_publication_event_uuid) if nc else None); assert ni==1 and len(nr)==2 and nc and nc.last_publication_event_uuid==later
        assert old_cursor and old_cursor.last_publish_sequence==1 and old_cursor.last_publication_event_uuid==EVENT
        print('previous_generation_cursor=',old_cursor.last_publish_sequence,str(old_cursor.last_publication_event_uuid),'new_generation_cursor=',nc.last_publish_sequence,str(nc.last_publication_event_uuid))
    print('PASS base HTTP B/D -> C; PASS new generation E + later event; independent cursors and deliveries')
finally:
    for p in reversed(PROCS): stop(p)

