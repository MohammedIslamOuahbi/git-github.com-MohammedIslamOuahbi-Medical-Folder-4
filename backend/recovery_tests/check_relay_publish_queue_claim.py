import sys,uuid
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy.orm import Session
from sqlalchemy import create_engine,select
from app.config import settings
from app.models.sync_transport import SyncTransportEvent,SyncRelayAuthorization
from app.models.sync_device import SyncDevice
from app.services.sync_transport_service import SyncTransportService
eng=create_engine(settings.database_url)
with Session(eng) as db:
 ev=db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.origin_kind=='inbox').order_by(SyncTransportEvent.id.desc()))
 if not ev: print('NO_INBOX_EVENT_FOR_RELAY_TEST'); raise SystemExit(0)
 carrier,pub,dst,pgen=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); ch='relay-'+ev.event_uuid.hex[:8]
 for d in (carrier,pub,dst): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='relay-'+d.hex,device_name='relay',registered_at=datetime.now(timezone.utc),is_active=True))
 db.add(SyncRelayAuthorization(carrier_device_uuid=carrier,origin_device_uuid=ev.source_device_uuid,origin_generation_uuid=ev.source_generation_uuid,destination_device_uuid=dst,channel=ch,created_at=datetime.now(timezone.utc),is_active=True));db.commit()
 s=SyncTransportService(); print('publish',s.publish_relay_event(db,event_uuid=ev.event_uuid,carrier_device_uuid=carrier,publisher_device_uuid=pub,publisher_generation_uuid=pgen,destination_device_uuid=dst,channel=ch)); print('queue',s.queue_for_peer(db,peer_device_uuid=dst,channel=ch,source_clinic_uuid=ev.source_clinic_uuid,source_generation_uuid=ev.source_generation_uuid,source_device_uuid=ev.source_device_uuid,limit=10)); claimed=s.claim_batch(db,peer_device_uuid=dst,channel=ch,limit=10); print('claim_count',len(claimed),'origin',claimed[0]['source_device_uuid'] if claimed else None,'publisher',claimed[0].get('publication_source_device_uuid') if claimed else None)
