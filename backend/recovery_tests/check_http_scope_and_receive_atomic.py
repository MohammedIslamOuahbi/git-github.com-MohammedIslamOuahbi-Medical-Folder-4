"""HTTP scope authorization and receive rollback hooks; synthetic data only."""
import os, sys, time, uuid, subprocess, requests
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox, SyncPublicationReceipt, SyncTransportCursor, SyncRelayAuthorization
from app.models.medical_visit import MedicalVisit
from app.services.sync_journal import payload_sha256
from app.services.central_sync_service import CentralSyncService
from sqlalchemy.engine import make_url

b=make_url(settings.database_url); ua=b.render_as_string(hide_password=False); ub=b.set(database="ibn_sina_transport_d").render_as_string(hide_password=False)
src, peer, other, gen, clinic, pub, pgen=(uuid.uuid4() for _ in range(7)); secret="stage4-scope-secret"; channel="scope-"+uuid.uuid4().hex[:8]; ids=[]; procs=[]
def start(url,port,stage=None):
    e=os.environ.copy();e["DATABASE_URL"]=url;e["PORT"]=str(port)
    cmd=[sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(port)]
    if stage: e["STAGE4_RECEIVE_FAILURE_STAGE"]=stage;cmd=[sys.executable,"recovery_tests/_run_api_receive_stage.py"]
    return subprocess.Popen(cmd,cwd=str(Path(__file__).resolve().parents[1]),env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def stop():
    for p in procs:p.terminate()
    for p in procs:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill()
def seed(url):
    from app.models.sync_device import SyncDevice
    with Session(create_engine(url)) as db:
        h=CentralSyncService()._hash_secret(secret)
        for ident in (src,peer,other): db.add(SyncDevice(uuid=ident,installation_uuid=uuid.uuid4(),device_code="scope-"+ident.hex,device_name="scope",registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
try:
    seed(ua);seed(ub);ea,eb=create_engine(ua),create_engine(ub)
    with Session(ea) as db:
        before_a=db.execute(select(MedicalVisit)).all()
        for n in range(3):
            x=uuid.uuid4();ids.append(x);p={"synthetic_atomic_id":x.hex};db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type="medical_visits",entity_uuid=uuid.uuid4(),operation="update",entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=10+n*20,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status="never_submitted",retry_count=0))
        db.commit()
    procs[:]=[start(ua,8891),start(ub,8892)];time.sleep(4);H={"X-Sync-Device-UUID":str(peer),"X-Sync-Device-Secret":secret}
    pull={"contract_version":"2.1","source_clinic_uuid":str(clinic),"source_device_uuid":str(src),"source_generation_uuid":str(gen),"channel":channel,"limit":3,"after_sequence":0,"publisher_device_uuid":str(pub),"publisher_generation_uuid":str(pgen),"publisher_clinic_uuid":str(clinic)};pr=requests.post("http://127.0.0.1:8891/api/v1/sync/v2/pull",json=pull,headers=H,timeout=10);pr.raise_for_status();events=pr.json()["data"]["events"];assert len(events)==3
    body={**pull,"events":events}
    # Authorization scope checks.
    assert requests.post("http://127.0.0.1:8892/api/v1/sync/v2/receive",json=body,headers={"X-Sync-Device-UUID":str(peer),"X-Sync-Device-Secret":"wrong"},timeout=10).status_code in (401,403)
    spoof=dict(body);spoof["source_device_uuid"]=str(other);assert requests.post("http://127.0.0.1:8892/api/v1/sync/v2/receive",json=spoof,headers=H,timeout=10).status_code in (403,409)
    badclinic=dict(body);badclinic["source_clinic_uuid"]=str(uuid.uuid4());assert requests.post("http://127.0.0.1:8892/api/v1/sync/v2/receive",json=badclinic,headers=H,timeout=10).status_code in (403,409)
    other_h={"X-Sync-Device-UUID":str(other),"X-Sync-Device-Secret":secret};cr=requests.post("http://127.0.0.1:8892/api/v1/sync/v2/cursor",json={"contract_version":"2.1","source_device_uuid":str(src),"source_generation_uuid":str(gen),"channel":channel,"publisher_device_uuid":str(pub),"publisher_generation_uuid":str(pgen),"publisher_clinic_uuid":str(clinic)},headers=other_h,timeout=10);assert cr.status_code in (401,403)
    # Three isolated failure points; every failed request must roll back completely.
    for stage in ("after_inbox","after_receipt","after_cursor"):
        stage_channel = channel + "-" + stage
        with Session(ea) as db:
            db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=stage_channel,created_at=datetime.now(timezone.utc),is_active=True)); db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=pub,origin_generation_uuid=pgen,destination_device_uuid=peer,channel=stage_channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
        with Session(eb) as db:
            db.add(SyncRelayAuthorization(carrier_device_uuid=peer,origin_device_uuid=src,origin_generation_uuid=gen,destination_device_uuid=peer,channel=stage_channel,created_at=datetime.now(timezone.utc),is_active=True)); db.commit()
        stage_pull = dict(pull); stage_pull["channel"] = stage_channel
        pr = requests.post("http://127.0.0.1:8891/api/v1/sync/v2/pull", json=stage_pull, headers=H, timeout=10); pr.raise_for_status()
        stage_events = pr.json()["data"]["events"]
        stage_body = dict(body); stage_body["channel"] = stage_channel; stage_body["events"] = stage_events
        stop();procs[:]=[start(ua,8891),start(ub,8892,stage)];time.sleep(4)
        with Session(eb) as db: before_cursor=db.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.source_device_uuid==src,SyncTransportCursor.source_generation_uuid==gen,SyncTransportCursor.channel==stage_channel)); before_n=db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))
        r=requests.post("http://127.0.0.1:8892/api/v1/sync/v2/receive",json=stage_body,headers=H,timeout=10);assert r.status_code==500
        with Session(eb) as db:
            assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==before_n
            assert db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid.in_(ids), SyncPublicationReceipt.channel==stage_channel))==0
            cur=db.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.source_device_uuid==src,SyncTransportCursor.source_generation_uuid==gen,SyncTransportCursor.channel==stage_channel));assert (cur.last_publish_sequence if cur else 0)==(before_cursor.last_publish_sequence if before_cursor else 0)
        # Hook is one-shot; retry succeeds and is then idempotent.
        ok=requests.post("http://127.0.0.1:8892/api/v1/sync/v2/receive",json=stage_body,headers=H,timeout=10);ok.raise_for_status()
        for ev in stage_events: requests.post("http://127.0.0.1:8891/api/v1/sync/v2/ack",json={"contract_version":"2.1","event_uuid":ev["event_uuid"],"channel":stage_channel,"lease_token":ev["lease_token"],"publisher_device_uuid":str(pub),"publisher_generation_uuid":str(pgen),"publisher_clinic_uuid":str(clinic)},headers=H,timeout=10).raise_for_status()
        with Session(eb) as db: assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(ids)))==3 and db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid.in_(ids), SyncPublicationReceipt.channel==stage_channel))==3
    with Session(ea) as db: assert db.execute(select(MedicalVisit)).all()==before_a
    print("PASS HTTP authorization scopes and atomic receive rollback; inbox/receipts/cursor unchanged on failure")
finally: stop()
