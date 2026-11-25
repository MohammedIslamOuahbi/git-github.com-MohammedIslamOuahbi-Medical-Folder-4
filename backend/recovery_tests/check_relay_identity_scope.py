import sys,uuid
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,'.')
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.config import settings
from app.models.sync_transport import SyncRelayAuthorization
from app.services.sync_transport_service import SyncTransportService
from app.exceptions import ForbiddenException
eng=create_engine(settings.database_url); a,b,g,d=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); ch='scope-'+a.hex[:8]
with Session(eng) as db:
 s=SyncTransportService()
 try:s.authorize_relay(db,carrier_device_uuid=a,origin_device_uuid=b,origin_generation_uuid=g,destination_device_uuid=d,channel=ch)
 except ForbiddenException as e: print('default_deny',e)
 db.add(SyncRelayAuthorization(carrier_device_uuid=a,origin_device_uuid=b,origin_generation_uuid=g,destination_device_uuid=d,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));db.commit()
 s.authorize_relay(db,carrier_device_uuid=a,origin_device_uuid=b,origin_generation_uuid=g,destination_device_uuid=d,channel=ch);print('authorized_scope=pass')
 try:s.authorize_relay(db,carrier_device_uuid=a,origin_device_uuid=b,origin_generation_uuid=g,destination_device_uuid=d,channel=ch+'x')
 except ForbiddenException:print('wrong_channel=reject')
