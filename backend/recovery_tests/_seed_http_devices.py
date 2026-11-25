import sys, uuid
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.services.central_sync_service import CentralSyncService
from sqlalchemy.engine import make_url
secret='stage4-http-secret'
source, receiver = uuid.uuid4(), uuid.uuid4()
for dbname in [make_url(settings.database_url).database, 'ibn_sina_transport_d']:
    url=make_url(settings.database_url).set(database=dbname)
    with Session(create_engine(url)) as db:
        for ident, code in [(source,'http-source-'+source.hex),(receiver,'http-receiver-'+receiver.hex)]:
            db.add(SyncDevice(uuid=ident, installation_uuid=uuid.uuid4(), device_code=code, device_name=code, registered_at=datetime.now(timezone.utc), is_active=True, central_secret_hash=CentralSyncService()._hash_secret(secret)))
        db.commit()
print(source, receiver)
