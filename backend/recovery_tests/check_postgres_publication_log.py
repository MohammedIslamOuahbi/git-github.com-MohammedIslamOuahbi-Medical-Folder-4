"""Synthetic publication-log acceptance checks; scoped cleanup only."""
import sys, uuid
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, delete, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventPublication, SyncPublicationCounter
from app.services.sync_transport_service import SyncTransportService
e=create_engine(settings.database_url); svc=SyncTransportService(); clinic,dev,gen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); ids=[]
with Session(e) as db:
    for i in range(4):
        x=uuid.uuid4(); ids.append(x); db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type="medical_visits",entity_uuid=uuid.uuid4(),operation="update",entity_version=1,payload={"synthetic":i},source_clinic_uuid=clinic,source_device_uuid=dev,source_generation_uuid=gen,source_sequence=100+i,schema_version=1,occurred_at=datetime.now(timezone.utc),central_status="never_submitted",retry_count=0))
    db.commit()
with Session(e) as db:
    assert svc.publish_committed(db,channel="central_server",limit=2)["has_more"]
with Session(e) as db:
    assert svc.publish_committed(db,channel="central_server",limit=10)["published"] == 2
    got=svc.publication_batch(db,source_device_uuid=dev,source_generation_uuid=gen,channel="central_server",limit=2)
    assert got["has_more"] and len(got["events"])==2
    got2=svc.publication_batch(db,source_device_uuid=dev,source_generation_uuid=gen,channel="central_server",after_sequence=got["cursor"],limit=2)
    assert not got2["has_more"] and len(got2["events"])==2
with Session(e) as db:
    assert svc.publish_committed(db,channel="central_server",limit=10)["published"] == 0
    db.execute(delete(SyncEventPublication).where(SyncEventPublication.event_uuid.in_(ids))); db.execute(delete(SyncPublicationCounter).where(SyncPublicationCounter.source_device_uuid==dev)); db.execute(delete(SyncChange).where(SyncChange.change_uuid.in_(ids))); db.commit()
print("PASS committed publication log, independent cursor batches, and idempotent publishers")
