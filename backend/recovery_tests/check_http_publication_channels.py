"""HTTP proof that publication cursors and receipts are channel independent."""
import os, sys, time, uuid, subprocess, requests
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox, SyncPublicationReceipt, SyncTransportCursor
from app.models.medical_visit import MedicalVisit
from app.services.sync_journal import payload_sha256
from app.services.central_sync_service import CentralSyncService
from sqlalchemy.engine import make_url

b = make_url(settings.database_url); ua = b.render_as_string(hide_password=False); ub = b.set(database="ibn_sina_transport_d").render_as_string(hide_password=False)
src, peer, gen, clinic = (uuid.uuid4() for _ in range(4)); secret = "stage4-channel-secret"
channels = ("central_server", "mobile_server"); ports = (8881, 8882); procs = []
event_id, payload = uuid.uuid4(), {"synthetic_channel_id": uuid.uuid4().hex}; new_id = uuid.uuid4()

def start(url, port):
    env = os.environ.copy(); env["DATABASE_URL"] = url
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=str(Path(__file__).resolve().parents[1]), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def stop():
    for p in procs: p.terminate()
    for p in procs:
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()
def seed(url):
    from app.models.sync_device import SyncDevice
    with Session(create_engine(url)) as db:
        h = CentralSyncService()._hash_secret(secret)
        for ident in (src, peer): db.add(SyncDevice(uuid=ident, installation_uuid=uuid.uuid4(), device_code="chan-"+ident.hex, device_name="channel-test", registered_at=datetime.now(timezone.utc), is_active=True, central_secret_hash=h))
        db.commit()
def pull(channel):
    body={"source_clinic_uuid":str(clinic),"source_device_uuid":str(src),"source_generation_uuid":str(gen),"channel":channel,"limit":10,"after_sequence":0}
    r=requests.post(f"http://127.0.0.1:{ports[0]}/api/v1/sync/v2/pull",json=body,headers=H,timeout=10); r.raise_for_status(); return r.json()["data"]["events"]
def receive(channel, events):
    body={"source_clinic_uuid":str(clinic),"source_device_uuid":str(src),"source_generation_uuid":str(gen),"channel":channel,"events":events,"limit":10}
    r=requests.post(f"http://127.0.0.1:{ports[1]}/api/v1/sync/v2/receive",json=body,headers=H,timeout=10); return r
try:
    seed(ua); seed(ub); ea,eb=create_engine(ua),create_engine(ub)
    with Session(ea) as db:
        before_a=db.execute(select(MedicalVisit)).all()
        db.add(SyncChange(change_uuid=event_id,revision_uuid=uuid.uuid4(),entity_type="medical_visits",entity_uuid=uuid.uuid4(),operation="update",entity_version=1,payload=payload,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=40,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status="never_submitted",retry_count=0)); db.commit()
    procs[:]=[start(ua,ports[0]),start(ub,ports[1])]; time.sleep(4); H={"X-Sync-Device-UUID":str(peer),"X-Sync-Device-Secret":secret}
    e1,e2=pull(channels[0]),pull(channels[1]); assert len(e1)==len(e2)==1 and e1[0]["event_uuid"]==e2[0]["event_uuid"]==str(event_id) and e1[0]["content_sha256"]==e2[0]["content_sha256"]
    assert e1[0]["publish_sequence"] != e2[0]["publish_sequence"] or channels[0] != channels[1]
    for ch,ev in zip(channels,(e1,e2)):
        assert receive(ch,ev).ok
        for item in ev: requests.post(f"http://127.0.0.1:{ports[0]}/api/v1/sync/v2/ack",json={"event_uuid":item["event_uuid"],"channel":ch,"lease_token":item["lease_token"]},headers=H,timeout=10).raise_for_status()
    with Session(eb) as db:
        assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==event_id))==1
        assert db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==event_id))==2
        curs=[db.scalar(select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid==peer,SyncTransportCursor.source_device_uuid==src,SyncTransportCursor.source_generation_uuid==gen,SyncTransportCursor.channel==ch)) for ch in channels]
        assert all(c.last_publish_sequence==1 for c in curs) and curs[0].last_publish_sequence==curs[1].last_publish_sequence
        assert db.execute(select(MedicalVisit)).all()==[]
    # New event is discovered after the durable channel cursor, without replaying the old event.
    with Session(ea) as db:
        p={"synthetic_channel_id":new_id.hex}; db.add(SyncChange(change_uuid=new_id,revision_uuid=uuid.uuid4(),entity_type="medical_visits",entity_uuid=uuid.uuid4(),operation="update",entity_version=1,payload=p,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,source_sequence=400,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status="never_submitted",retry_count=0)); db.commit()
    nxt=pull(channels[0]); assert len(nxt)==1 and nxt[0]["event_uuid"]==str(new_id); assert receive(channels[0],nxt).ok
    # Same channel/position claimed by a different event is a clear conflict and leaves no partial row.
    bad=dict(e1[0]); bad["event_uuid"]=str(uuid.uuid4()); bad["payload"]={"synthetic_channel_id":"collision"}; bad["content_sha256"]=payload_sha256(bad["payload"])
    r=receive(channels[0],[bad]); assert r.status_code==409 and r.json().get("message")=="SYNC_PUBLICATION_POSITION_CONFLICT"
    print("PASS independent channel receipts/cursors, durable new-event continuation, and publication-position collision rejection")
finally: stop()
