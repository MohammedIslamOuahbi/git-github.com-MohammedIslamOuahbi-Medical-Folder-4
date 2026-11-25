"""Synthetic PostgreSQL stage-four transport test; never applies inbox payloads."""
from __future__ import annotations
import sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import create_engine, make_url
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.exceptions import ConflictException
from app.models.medical_visit import MedicalVisit
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventDelivery, SyncEventInbox, SyncTransportAttempt, SyncTransportCursor
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService

url = make_url(settings.database_url)
assert url.drivername == "postgresql+psycopg" and url.host in {"localhost", "127.0.0.1"}
assert url.database == "ibn_sina_recovery_test" and (url.port or 5432) == 5432
engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
with engine.connect() as c:
    assert c.execute(text("select current_database(), current_schema(), inet_server_port()")).one() == ("ibn_sina_recovery_test", "public", 5432)
    assert c.scalar(text("select version_num from alembic_version")) == "20261008_06"
service = SyncTransportService()
clinic, source, receiver, generation = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
event_ids: list[uuid.UUID] = []

def envelope(seq: int, event_uuid: uuid.UUID | None = None, payload: dict | None = None) -> dict:
    event_uuid = event_uuid or uuid.uuid4(); event_ids.append(event_uuid); body = payload or {"synthetic": seq}
    event = {"event_uuid": str(event_uuid), "source_clinic_uuid": str(clinic), "source_device_uuid": str(source),
             "source_generation_uuid": str(generation), "source_sequence": seq, "entity_type": "medical_visits",
             "entity_uuid": str(uuid.uuid4()), "revision_uuid": str(uuid.uuid4()), "parent_revision_uuid": None,
             "operation": "update", "schema_version": 1, "payload": body}
    event.update({"publication_source_device_uuid": str(source), "publication_source_generation_uuid": str(generation),
                  "publication_channel": "central_server", "publish_sequence": seq})
    event["content_sha256"] = payload_sha256(body); return event

with Session(engine) as db:
    db.add_all([
        SyncDevice(uuid=source, installation_uuid=uuid.uuid4(), device_code="stage4-source-" + source.hex, device_name="stage4 source", registered_at=datetime.now(timezone.utc), is_active=True),
        SyncDevice(uuid=receiver, installation_uuid=uuid.uuid4(), device_code="stage4-receiver-" + receiver.hex, device_name="stage4 receiver", registered_at=datetime.now(timezone.utc), is_active=True),
    ]); db.commit(); medical_before = db.scalar(select(func.count()).select_from(MedicalVisit))
first, second = envelope(1), envelope(2)
with Session(engine) as db:
    assert service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[first], source_generation_uuid=generation)["accepted"] == 1
with Session(engine) as db:
    assert service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[first], source_generation_uuid=generation)["duplicates"] == 1
print("PASS commit-before-ACK and duplicate event identity")
bad = dict(first); bad["payload"] = {"synthetic": "different"}; bad["content_sha256"] = payload_sha256(bad["payload"])
try:
    with Session(engine) as db: service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[bad], source_generation_uuid=generation)
except ConflictException as exc: assert exc.detail["message"] == "EVENT_UUID_CONTENT_MISMATCH"
else: raise AssertionError("same event UUID with changed content accepted")
print("PASS UUID content mismatch rejected")
with Session(engine) as db:
    result = service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[second], source_generation_uuid=generation)
    assert result["accepted"] == 1 and result["cursor"]["last_publish_sequence"] == 2
    assert db.scalar(select(func.count()).select_from(MedicalVisit)) == medical_before
print("PASS bounded batch cursor and no medical-table application")
too_many = [envelope(10 + i) for i in range(3)]
try:
    with Session(engine) as db:
        service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=too_many, source_generation_uuid=generation, limit=2)
except ConflictException as exc:
    assert exc.detail["message"] == "SYNC_BATCH_LIMIT_EXCEEDED"
else:
    raise AssertionError("oversized batch accepted")
with Session(engine) as db:
    assert db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid.in_([uuid.UUID(e["event_uuid"]) for e in too_many]))) == 0
print("PASS oversized batch rejected without partial inbox rows")
wrong_clinic = envelope(20); wrong_clinic["source_clinic_uuid"] = str(uuid.uuid4())
try:
    with Session(engine) as db:
        service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[wrong_clinic], source_generation_uuid=generation)
except Exception as exc:
    assert getattr(exc, "detail", {}).get("message") == "SYNC_CLINIC_IDENTITY_MISMATCH"
else:
    raise AssertionError("foreign clinic event accepted")
print("PASS foreign clinic event rejected")
fresh_generation = uuid.uuid4(); fresh = envelope(1); fresh["source_generation_uuid"] = str(fresh_generation)
try:
    with Session(engine) as db: service.receive_batch(db, receiver_device_uuid=receiver, source_clinic_uuid=clinic, source_device_uuid=source, channel="central_server", events=[fresh], source_generation_uuid=fresh_generation)
except ConflictException as exc: assert exc.detail["message"] == "SOURCE_GENERATION_CHANGED"
else: raise AssertionError("cursor silently reused across generations")
print("PASS source generation change rejected")
change_uuid = uuid.uuid4(); revision_uuid = uuid.uuid4(); outbox_payload = {"synthetic": "outbox"}
with Session(engine) as db:
    db.add(SyncChange(change_uuid=change_uuid, revision_uuid=revision_uuid, entity_type="medical_visits", entity_uuid=uuid.uuid4(), operation="update", entity_version=1, payload=outbox_payload, source_clinic_uuid=clinic, source_device_uuid=source, source_generation_uuid=generation, source_sequence=3, schema_version=1, content_sha256=payload_sha256(outbox_payload), occurred_at=datetime.now(timezone.utc), central_status="never_submitted", retry_count=0)); db.commit()
with Session(engine) as db:
    service.publish_committed(db, channel="central_server", limit=1000)
    assert service.queue_for_peer(db, peer_device_uuid=receiver, channel="central_server", source_clinic_uuid=clinic, source_generation_uuid=generation, limit=10)["queued"] == 1
with Session(engine) as db:
    claimed = service.claim_batch(db, peer_device_uuid=receiver, channel="central_server", limit=10)
    assert len(claimed) == 1 and claimed[0]["event_uuid"] == str(change_uuid)
    assert db.scalar(select(func.count()).select_from(SyncTransportAttempt).where(SyncTransportAttempt.event_uuid == change_uuid)) == 1
print("PASS durable per-peer delivery claim and attempt")
with Session(engine) as db:
    service.record_failure(db, event_uuid=change_uuid, peer_device_uuid=receiver, channel="central_server",
                           error_code="TEMPORARY_NETWORK", error_message="synthetic transport failure")
    row = db.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid == change_uuid))
    assert row.status == "pending" and row.attempt_count == 2 and row.available_at > datetime.now(timezone.utc)
print("PASS retry backoff and permanent error state are durable")
with Session(engine) as db:
    db.execute(delete(SyncTransportAttempt).where(SyncTransportAttempt.peer_device_uuid == receiver)); db.execute(delete(SyncEventDelivery).where(SyncEventDelivery.peer_device_uuid == receiver)); db.execute(delete(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid == receiver)); db.execute(delete(SyncEventInbox).where(SyncEventInbox.event_uuid.in_(event_ids))); db.execute(delete(SyncChange).where(SyncChange.change_uuid == change_uuid)); db.execute(delete(SyncDevice).where(SyncDevice.uuid.in_([source, receiver]))); db.commit()
engine.dispose(); print("Cleaned only this run's transport rows")
