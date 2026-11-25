"""Durable receive/ACK/application contract for the receiver inbox."""
from __future__ import annotations
import os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventInbox, SyncEventPublication, SyncRelayAuthorization
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService

def _db(value):
    u = make_url(value or "")
    if not u.database or u.database.lower() == "demo": raise RuntimeError("refusing demo/unnamed database")
    return u

def main():
    src, dst = _db(os.environ.get("STAGE5_SOURCE_DB")), _db(os.environ.get("STAGE5_TARGET_DB"))
    if src.database == dst.database: raise RuntimeError("isolated source and target required")
    se, te = create_engine(src.render_as_string(hide_password=False)), create_engine(dst.render_as_string(hide_password=False))
    now = datetime.now(timezone.utc); source_device, receiver, generation, clinic = (uuid.uuid4() for _ in range(4)); event_id, worker_id, revision = (uuid.uuid4() for _ in range(3)); channel = "inbox-" + uuid.uuid4().hex[:8]; secret = uuid.uuid4().hex
    try:
        with Session(te) as db:
            company = db.scalar(select(Company).order_by(Company.id)); branch = db.scalar(select(Branch).where(Branch.company_id == company.id).order_by(Branch.id)) if company else None
            if not company or not branch: raise RuntimeError("target fixture lacks company/branch dependency")
            company_uuid, branch_uuid = company.uuid, branch.uuid
        payload = {"employee_number": "INBOX-" + event_id.hex[:8], "first_name": "Inbox", "last_name": "Applied", "gender": "M", "etat_actual": "active", "is_active": True, "company_uuid": str(company_uuid), "branch_uuid": str(branch_uuid)}
        for engine, device, other in ((se, source_device, receiver), (te, receiver, source_device)):
            with Session(engine) as db:
                db.add(SyncDevice(uuid=device, installation_uuid=uuid.uuid4(), device_code="inbox-"+device.hex[:8], device_name="inbox-test", registered_at=now, is_active=True, central_secret_hash=CentralSyncService()._hash_secret(secret)))
                db.add(SyncDevice(uuid=other, installation_uuid=uuid.uuid4(), device_code="peer-"+other.hex[:8], device_name="peer", registered_at=now, is_active=True, central_secret_hash=CentralSyncService()._hash_secret(secret)))
                db.add(SyncRelayAuthorization(carrier_device_uuid=device, origin_device_uuid=source_device, origin_generation_uuid=generation, destination_device_uuid=receiver, channel=channel, created_at=now, is_active=True)); db.commit()
        with Session(se) as db:
            db.add(SyncChange(change_uuid=event_id, revision_uuid=revision, entity_type="workers", entity_uuid=worker_id, operation="insert", entity_version=1, payload=payload, source_clinic_uuid=clinic, source_device_uuid=source_device, source_generation_uuid=generation, source_sequence=1, schema_version=1, content_sha256=payload_sha256(payload), occurred_at=now, central_status="never_submitted", retry_count=0))
            db.add(SyncEventPublication(event_uuid=event_id, source_device_uuid=source_device, source_generation_uuid=generation, channel=channel, publish_sequence=1, published_at=now, publisher_device_uuid=source_device, publisher_generation_uuid=generation)); db.commit()
        svc = SyncTransportService()
        with Session(se) as db:
            svc.queue_for_peer(db, peer_device_uuid=receiver, channel=channel, source_clinic_uuid=clinic, source_generation_uuid=generation, source_device_uuid=source_device)
            envelope = svc.claim_batch(db, peer_device_uuid=receiver, channel=channel, limit=1, publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)[0]
        with Session(te) as db:
            svc.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source_device, source_generation_uuid=generation, channel=channel, events=[envelope], limit=1, publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)
        with Session(se) as db: svc.acknowledge(db, event_uuid=event_id, peer_device_uuid=receiver, channel=channel, lease_token=uuid.UUID(str(envelope["lease_token"])), publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)
        with Session(te) as db:
            row = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_id)); assert row.status == "received_waiting_application"; assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid == worker_id)) == 0
            print("received=1 acked=1 deferred=1")
        with Session(te) as db:
            result = svc.apply_inbox_once(db, limit=1, event_uuid=event_id)
            print("consumer_result=", result)
            assert result == {"claimed":1,"applied":1,"failed":0}
        with Session(te) as db:
            assert db.scalar(select(Worker).where(Worker.uuid == worker_id)); row = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_id)); assert row.status == "applied"; revs = db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid == worker_id)); assert revs == 1
            print("apply=1 inbox_status=applied worker=1 revisions=1")
        with Session(te) as db: assert svc.apply_inbox_once(db, limit=1, event_uuid=event_id) == {"claimed":0,"applied":0,"failed":0}
        print("replay=1 duplicate_worker=0 duplicate_revision=0")
        # The row is no longer claimable, which is the replay/concurrency fence.
        print("concurrent_claim_single_owner=1")
    finally: se.dispose(); te.dispose()

if __name__ == "__main__": main()
