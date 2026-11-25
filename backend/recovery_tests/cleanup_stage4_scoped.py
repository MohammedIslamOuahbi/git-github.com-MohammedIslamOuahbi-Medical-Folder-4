import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import delete, select
from app.database import SessionLocal
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventInbox, SyncEventDelivery, SyncTransportCursor, SyncTransportAttempt
from app.models.sync_change import SyncChange
with SessionLocal() as db:
    devices = db.scalars(select(SyncDevice).where(SyncDevice.device_code.like("stage4-%"))).all()
    ids = [item.uuid for item in devices]
    db.execute(delete(SyncTransportAttempt).where(SyncTransportAttempt.peer_device_uuid.in_(ids)))
    db.execute(delete(SyncEventDelivery).where(SyncEventDelivery.peer_device_uuid.in_(ids)))
    db.execute(delete(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid.in_(ids)))
    db.execute(delete(SyncEventInbox).where(SyncEventInbox.source_device_uuid.in_(ids)))
    db.execute(delete(SyncChange).where(SyncChange.source_device_uuid.in_(ids)))
    db.execute(delete(SyncDevice).where(SyncDevice.uuid.in_(ids)))
    db.commit()
print(f"cleaned scoped stage4 devices: {len(ids)}")
