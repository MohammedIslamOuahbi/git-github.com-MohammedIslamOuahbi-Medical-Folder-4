"""Focused transport contract: ACK is durable delivery, not entity application."""
from __future__ import annotations
import os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.models.medical_visit import MedicalVisit
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventInbox, SyncEventDelivery, SyncRelayAuthorization, SyncEventPublication
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService

def _db(value):
    parsed = make_url(value or "")
    if not parsed.database or parsed.database.lower() == "demo": raise RuntimeError("refusing demo or unnamed database")
    return parsed

def main():
    source = _db(os.environ.get("STAGE5_SOURCE_DB")); target = _db(os.environ.get("STAGE5_TARGET_DB"))
    if source.database == target.database: raise RuntimeError("source and target databases must differ")
    se, te = create_engine(source.render_as_string(hide_password=False)), create_engine(target.render_as_string(hide_password=False))
    source_device, receiver_device, generation, clinic = (uuid.uuid4() for _ in range(4))
    event_uuid, entity_uuid, revision_uuid, channel = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), f"ack-{uuid.uuid4().hex[:8]}"
    secret, now, payload = uuid.uuid4().hex, datetime.now(timezone.utc), {"synthetic_test_id": event_uuid.hex}
    try:
        for engine, device in ((se, source_device), (te, receiver_device)):
            with Session(engine) as db:
                db.add(SyncDevice(uuid=device, installation_uuid=uuid.uuid4(), device_code=f"ack-{device.hex[:8]}", device_name="ack-test", registered_at=now, is_active=True, central_secret_hash=CentralSyncService()._hash_secret(secret)))
                other = receiver_device if device == source_device else source_device
                db.add(SyncDevice(uuid=other, installation_uuid=uuid.uuid4(), device_code=f"ack-{other.hex[:8]}", device_name="ack-peer", registered_at=now, is_active=True, central_secret_hash=CentralSyncService()._hash_secret(secret)))
                db.add(SyncRelayAuthorization(carrier_device_uuid=device, origin_device_uuid=source_device, origin_generation_uuid=generation, destination_device_uuid=receiver_device, channel=channel, created_at=now, is_active=True)); db.commit()
        with Session(se) as db:
            db.add(SyncChange(change_uuid=event_uuid, revision_uuid=revision_uuid, entity_type="medical_visits", entity_uuid=entity_uuid, operation="insert", entity_version=1, payload=payload, source_clinic_uuid=clinic, source_device_uuid=source_device, source_generation_uuid=generation, source_sequence=1, schema_version=1, content_sha256=payload_sha256(payload), occurred_at=now, central_status="never_submitted", retry_count=0))
            db.add(SyncEventPublication(event_uuid=event_uuid, source_device_uuid=source_device, source_generation_uuid=generation, channel=channel, publish_sequence=1, published_at=now, publisher_device_uuid=source_device, publisher_generation_uuid=generation)); db.commit()
        svc = SyncTransportService()
        with Session(se) as db:
            queued = svc.queue_for_peer(db, peer_device_uuid=receiver_device, channel=channel, source_clinic_uuid=clinic, source_generation_uuid=generation, source_device_uuid=source_device, limit=10)
            envelope = svc.claim_batch(db, peer_device_uuid=receiver_device, channel=channel, limit=10, publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)[0]
            assert queued["queued"] == 1
        with Session(te) as db:
            result = svc.receive_batch(db, receiver_device_uuid=receiver_device, source_clinic_uuid=clinic, source_device_uuid=source_device, source_generation_uuid=generation, channel=channel, events=[envelope], limit=10, publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)
            assert result["accepted"] == 1
        with Session(te) as db:
            inbox = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_uuid)); assert inbox and inbox.status == "received_waiting_application"
            assert db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid == entity_uuid)) == 0
            print("receive_commit=1 inbox_status=received_waiting_application entity_applied=0")
        with Session(se) as db:
            svc.acknowledge(db, event_uuid=event_uuid, peer_device_uuid=receiver_device, channel=channel, lease_token=uuid.UUID(str(envelope["lease_token"])), publisher_device_uuid=source_device, publisher_generation_uuid=generation, publisher_clinic_uuid=clinic)
        with Session(se) as db:
            delivery = db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid == event_uuid, SyncEventDelivery.channel == channel)); assert delivery and delivery.status == "delivered"
            print("ack=committed sender_delivery=delivered sender_resend_eligible=0")
        with Session(te) as db:
            inbox = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_uuid)); assert inbox and inbox.status == "received_waiting_application"
            assert db.scalar(select(func.count()).select_from(MedicalVisit).where(MedicalVisit.uuid == entity_uuid)) == 0
            # This contract intentionally stops before the consumer is started;
            # application is covered by check_sync_event_inbox_application.py.
            print("post_ack_receiver_inbox=durable application_outcome=pending entity_applied=0 recovery_consumer=not_started_by_setup")
    finally:
        se.dispose(); te.dispose()

if __name__ == "__main__": main()
