import sys,uuid
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventInbox,SyncTransportEvent,SyncPublicationReceipt
from app.models.medical_visit import MedicalVisit
from app.services.central_sync_service import CentralSyncService
from app.services.sync_transport_service import SyncTransportService
from app.services.sync_journal import payload_sha256
eng=create_engine(settings.database_url); src,recv,gen,clinic,ev=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); ch='verify-rx-'+ev.hex[:8]
with Session(eng) as db:
 h=CentralSyncService()._hash_secret('verify-rx-secret')
 for d in (src,recv): db.add(SyncDevice(uuid=d,installation_uuid=uuid.uuid4(),device_code='rx-'+d.hex,device_name='rx',registered_at=datetime.now(timezone.utc),central_secret_hash=h,is_active=True))
 db.commit()
p={'synthetic_receive':ev.hex}; base={'event_uuid':str(ev),'source_clinic_uuid':str(clinic),'source_device_uuid':str(src),'source_generation_uuid':str(gen),'source_sequence':42,'entity_type':'medical_visits','entity_uuid':str(uuid.uuid4()),'revision_uuid':str(uuid.uuid4()),'operation':'update','schema_version':1,'payload':p,'content_sha256':payload_sha256(p),'publication_channel':ch,'publish_sequence':1,'publication_source_device_uuid':str(src),'publication_source_generation_uuid':str(gen)}
def call(e,stage=None):
 with Session(eng) as db: return SyncTransportService().receive_batch(db,receiver_device_uuid=recv,source_clinic_uuid=clinic,source_device_uuid=src,source_generation_uuid=gen,channel=ch,events=[e],limit=10,_failure_stage=stage,publisher_device_uuid=src,publisher_generation_uuid=gen,publisher_clinic_uuid=clinic)
print('first',call(base))
with Session(eng) as db: print('durable',db.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==ev)),db.scalar(select(func.count()).select_from(SyncTransportEvent).where(SyncTransportEvent.event_uuid==ev)),db.scalar(select(func.count()).select_from(SyncPublicationReceipt).where(SyncPublicationReceipt.event_uuid==ev)))
print('duplicate',call(base))
import concurrent.futures
ce=dict(base); ce['event_uuid']=str(uuid.uuid4()); ce['entity_uuid']=str(uuid.uuid4()); ce['revision_uuid']=str(uuid.uuid4()); ce['source_sequence']=77; ce['publish_sequence']=2; ce['payload']={'concurrent':True}; ce['content_sha256']=payload_sha256(ce['payload'])
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(call,[ce,ce]))
print('concurrent_results',results)
with Session(eng) as db: assert db.scalar(select(func.count()).select_from(SyncTransportEvent).where(SyncTransportEvent.event_uuid==uuid.UUID(ce['event_uuid'])))==1
for altered in ({'payload':{'different':True}},{'source_device_uuid':str(uuid.uuid4())}):
 x=dict(base);x.update(altered);x['content_sha256']=payload_sha256(x['payload'])
 try: call(x)
 except Exception as ex: print('mismatch_rejected',type(ex).__name__)
for stage in ('after_source','after_inbox','after_receipt','after_cursor'):
 x=dict(base);x['event_uuid']=str(uuid.uuid4());x['entity_uuid']=str(uuid.uuid4());x['revision_uuid']=str(uuid.uuid4());x['source_sequence']+=100; x['publish_sequence']+=100; x['payload']={'synthetic_failure':stage};x['content_sha256']=payload_sha256(x['payload'])
 try: call(x,stage)
 except Exception as ex: print('rollback',stage,type(ex).__name__)
with Session(eng) as db: print('medical_rows',db.scalar(select(func.count()).select_from(MedicalVisit)))
print('PASS receive/source durability and mismatch checks')




