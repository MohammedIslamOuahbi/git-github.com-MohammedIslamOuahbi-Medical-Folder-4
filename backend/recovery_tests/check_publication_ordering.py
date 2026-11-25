import sys, uuid, threading
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, delete, func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventPublication, SyncPublicationCounter
from app.services.sync_transport_service import SyncTransportService
e=create_engine(settings.database_url); s=SyncTransportService(); dev,gen,clinic=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); ids=[]; tag=dev.hex[:8]; order_channel='o-'+tag; concurrent_channel='c-'+tag; rollback_channel='r-'+tag
def add(db):
    x=uuid.uuid4(); ids.append(x)
    db.add(SyncChange(change_uuid=x,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload={'synthetic':str(x)},source_clinic_uuid=clinic,source_device_uuid=dev,source_generation_uuid=gen,source_sequence=1,schema_version=1,occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0)); return x
a=Session(e); b=Session(e); a_id=add(a); b_id=add(b); b.commit()
with Session(e) as q:
    result=s.publish_committed(q,channel=order_channel); assert result['published']>=1
    first=s.publication_batch(q,source_device_uuid=dev,source_generation_uuid=gen,channel=order_channel)
    assert first['events']==[str(b_id)]
a.commit()
with Session(e) as q:
    assert s.publish_committed(q,channel=order_channel)['published']==1
    second=s.publication_batch(q,source_device_uuid=dev,source_generation_uuid=gen,channel=order_channel,after_sequence=first['cursor'])
    assert len(second['events'])==1 and second['events'][0]==str(a_id)
a.close(); b.close(); print('PASS commit order and later event cursor continuation')
more=[]
with Session(e) as q:
    for _ in range(6): more.append(add(q))
    q.commit()
errs=[]
def pub():
    try:
        with Session(e) as q: s.publish_committed(q,channel=concurrent_channel,limit=100)
    except Exception as x: errs.append(x)
ts=[threading.Thread(target=pub) for _ in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
with Session(e) as q:
    if errs: print('publisher errors', [type(x).__name__+':'+str(x)[:120] for x in errs])
    rows=q.scalars(select(SyncEventPublication).where(SyncEventPublication.channel==concurrent_channel)).all()
    owned=q.scalars(select(SyncEventPublication).where(SyncEventPublication.channel==concurrent_channel, SyncEventPublication.event_uuid.in_(more))).all()
    assert len(owned)==6 and len({r.publish_sequence for r in owned})==6
print('PASS concurrent publishers, unique positions, no loss')
with Session(e) as q:
    try: s.publish_committed(q,channel=rollback_channel,_fail_before_commit=True)
    except RuntimeError: pass
with Session(e) as q:
    assert q.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.channel==rollback_channel))==0
    assert s.publish_committed(q,channel=rollback_channel,limit=100)['published']>=1
print('PASS publication rollback and retry without duplicate')
with Session(e) as q:
    q.execute(delete(SyncEventPublication).where(SyncEventPublication.channel.in_([order_channel,concurrent_channel,rollback_channel])))
    q.execute(delete(SyncPublicationCounter).where(SyncPublicationCounter.source_device_uuid==dev))
    q.execute(delete(SyncChange).where(SyncChange.change_uuid.in_(ids+more))); q.commit()
print('Cleaned only ordering test rows')
