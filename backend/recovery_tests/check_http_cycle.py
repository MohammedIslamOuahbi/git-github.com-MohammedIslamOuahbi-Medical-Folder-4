import os, sys, uuid, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
import requests
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy.engine import make_url
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox, SyncEventDelivery, SyncTransportEvent, SyncPublicationReceipt, SyncTransportCursor
from app.models.sync_transport import SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.sync_journal import payload_sha256
from app.services.central_sync_service import CentralSyncService
BASE=make_url(settings.database_url)
DB_A=BASE.database
DB_B='ibn_sina_transport_d'
URL_A=BASE.render_as_string(hide_password=False)
URL_B=BASE.set(database=DB_B).render_as_string(hide_password=False)
source, receiver, generation, clinic = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
secret='stage4-cycle-secret'
event_id, entity_id, revision_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
channel='cycle-'+event_id.hex[:8]
payload={'synthetic_test_id': event_id.hex}
def dburl(name): return BASE.set(database=name).render_as_string(hide_password=False)
def verify_db(url, expected):
    with create_engine(url).connect() as c:
        name, schema = c.exec_driver_sql("select current_database(), current_schema()").one()
        rev = c.exec_driver_sql("select version_num from alembic_version").scalar()
        assert name == expected and schema == "public" and rev == "20261008_15"
    print(f"DB verified name={expected} schema=public alembic=20261008_15")
def seed(url):
    from app.models.sync_device import SyncDevice
    e=create_engine(url)
    with Session(e) as db:
        h=CentralSyncService()._hash_secret(secret)
        for ident in (source, receiver):
            if db.scalar(select(SyncDevice).where(SyncDevice.uuid==ident)) is None:
                db.add(SyncDevice(uuid=ident, installation_uuid=uuid.uuid4(), device_code='cycle-'+ident.hex, device_name='cycle', registered_at=datetime.now(timezone.utc), is_active=True, central_secret_hash=h))
        if db.scalar(select(SyncRelayAuthorization.id).where(SyncRelayAuthorization.carrier_device_uuid==receiver, SyncRelayAuthorization.origin_device_uuid==source, SyncRelayAuthorization.origin_generation_uuid==generation, SyncRelayAuthorization.destination_device_uuid==receiver, SyncRelayAuthorization.channel==channel)) is None:
            db.add(SyncRelayAuthorization(carrier_device_uuid=receiver, origin_device_uuid=source, origin_generation_uuid=generation, destination_device_uuid=receiver, channel=channel, created_at=datetime.now(timezone.utc), is_active=True))
        db.commit()
def start(url, port):
    env=os.environ.copy(); env['DATABASE_URL']=url
    log=Path(__file__).with_name(f"cycle-api-{port}.log")
    return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)], cwd=str(Path(__file__).resolve().parents[1]), env=env, stdout=subprocess.DEVNULL, stderr=log.open('w',encoding='utf-8'))
def ready(proc, port):
    end=time.time()+20
    while time.time()<end:
        if proc.poll() is not None:
            raise RuntimeError(f"API {port} exited with code {proc.returncode}; see cycle-api-{port}.log")
        try:
            r=requests.get(f"http://127.0.0.1:{port}/openapi.json",timeout=1)
            if r.status_code==200:
                return
        except requests.RequestException: pass
        time.sleep(.2)
    raise RuntimeError(f"API {port} readiness timeout")
procs=[]
def migrate(url):
    env=os.environ.copy(); env["DATABASE_URL"]=url
    r=subprocess.run([sys.executable,"-m","alembic","upgrade","head"],cwd=str(Path(__file__).resolve().parents[1]),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    if r.returncode != 0: raise RuntimeError("Alembic upgrade failed for isolated test database")
try:
    migrate(URL_A); migrate(URL_B)
    verify_db(URL_A, DB_A); verify_db(URL_B, DB_B)
    seed(URL_A); seed(URL_B)
    ea=create_engine(URL_A)
    before_a=None
    with Session(ea) as db:
        before_a=db.scalar(select(func.count()).select_from(MedicalVisit))
        db.add(SyncChange(change_uuid=event_id, revision_uuid=revision_id, entity_type='medical_visits', entity_uuid=entity_id, operation='update', entity_version=1, payload=payload, source_clinic_uuid=clinic, source_device_uuid=source, source_generation_uuid=generation, source_sequence=1, schema_version=1, content_sha256=payload_sha256(payload), occurred_at=datetime.now(timezone.utc), central_status='never_submitted', retry_count=0)); db.commit()
    procs=[start(URL_A,8821), start(URL_B,8822)]; ready(procs[0],8821); ready(procs[1],8822)
    headers={'X-Sync-Device-UUID':str(receiver),'X-Sync-Device-Secret':secret}
    pull={'source_clinic_uuid':str(clinic),'source_device_uuid':str(source),'source_generation_uuid':str(generation),'channel':channel,'limit':10,'after_sequence':0,'contract_version':'2.1','publisher_device_uuid':str(source),'publisher_generation_uuid':str(generation),'publisher_clinic_uuid':str(clinic)}
    pr=requests.post('http://127.0.0.1:8821/api/v1/sync/v2/pull',json=pull,headers=headers,timeout=10); pr.raise_for_status(); events=pr.json()['data']['events']
    assert len(events)==1 and events[0]['event_uuid']==str(event_id)
    envelope=events[0]; assert envelope['content_sha256']==payload_sha256(payload)
    receive={'source_clinic_uuid':str(clinic),'source_device_uuid':str(source),'source_generation_uuid':str(generation),'channel':channel,'events':[envelope],'limit':10,'contract_version':'2.1','publisher_device_uuid':str(source),'publisher_generation_uuid':str(generation),'publisher_clinic_uuid':str(clinic)}
    rh={'X-Sync-Device-UUID':str(receiver),'X-Sync-Device-Secret':secret}
    rr=requests.post('http://127.0.0.1:8822/api/v1/sync/v2/receive',json=receive,headers=rh,timeout=10); rr.raise_for_status(); assert rr.json()['data']['accepted']==1
    eb=create_engine(URL_B)
    with Session(eb) as db:
        row=db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id)); assert row and row.status=='received_waiting_application'
        assert db.scalar(select(func.count()).select_from(MedicalVisit))==0
    ack={'event_uuid':str(event_id),'channel':channel,'lease_token':envelope['lease_token'],'contract_version':'2.1','publisher_device_uuid':str(source),'publisher_generation_uuid':str(generation),'publisher_clinic_uuid':str(clinic)}
    ar=requests.post('http://127.0.0.1:8821/api/v1/sync/v2/ack',json=ack,headers=headers,timeout=10); ar.raise_for_status()
    with Session(ea) as db:
        d=db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==event_id,SyncEventDelivery.channel==channel)); assert d and d.status=='delivered'
        assert db.scalar(select(func.count()).select_from(MedicalVisit))==before_a
    # Contract rejection matrix; each case is HTTP-only and must not produce a 500.
    cases=[]
    missing=dict(pull); missing.pop("publisher_device_uuid")
    cases.append(("pull-missing-publisher", requests.post("http://127.0.0.1:8821/api/v1/sync/v2/pull",json=missing,headers=headers,timeout=10)))
    old=dict(pull); old["contract_version"]="2.0"
    cases.append(("pull-old-contract", requests.post("http://127.0.0.1:8821/api/v1/sync/v2/pull",json=old,headers=headers,timeout=10)))
    cases.append(("pull-invalid-device", requests.post("http://127.0.0.1:8821/api/v1/sync/v2/pull",json=pull,headers={"X-Sync-Device-UUID":str(receiver),"X-Sync-Device-Secret":"wrong"},timeout=10)))
    bad_scope=dict(receive); bad_scope["publisher_device_uuid"]=str(uuid.uuid4())
    cases.append(("receive-scope-mismatch", requests.post("http://127.0.0.1:8822/api/v1/sync/v2/receive",json=bad_scope,headers=rh,timeout=10)))
    bad_ack=dict(ack); bad_ack["lease_token"]=str(uuid.uuid4())
    cases.append(("ack-wrong-token", requests.post("http://127.0.0.1:8821/api/v1/sync/v2/ack",json=bad_ack,headers=headers,timeout=10)))
    repeat=requests.post("http://127.0.0.1:8821/api/v1/sync/v2/ack",json=ack,headers=headers,timeout=10)
    cases.append(("ack-repeat-valid", repeat))
    for name,resp in cases:
        print(f"REJECT {name} http={resp.status_code}")
        assert resp.status_code != 500
    with Session(ea) as db:
        assert db.scalar(select(SyncEventDelivery.status).where(SyncEventDelivery.event_uuid==event_id,SyncEventDelivery.channel==channel)) == 'delivered'
    with Session(eb) as db:
        assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id)) == 1
    print('PASS HTTP pull -> receive -> durable ack; rejection matrix completed; one inbox row; medical tables unchanged')
finally:
    for p in procs:
        p.terminate()
    for p in procs:
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()

