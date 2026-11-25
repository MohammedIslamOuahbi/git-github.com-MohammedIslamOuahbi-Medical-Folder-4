import sys, uuid, threading, time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncTransportEvent, SyncEventPublication, SyncPublicationCounter, SyncRelayAuthorization
from app.services.sync_transport_service import SyncTransportService
from app.services.sync_journal import payload_sha256

engine=create_engine(settings.database_url, pool_pre_ping=True)
CLINIC,B,D,G1,G2=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); CH='scope-'+uuid.uuid4().hex[:8]
def add_change(db,eid,origin,seq):
 p={'scope_test':eid.hex}; db.add(SyncChange(change_uuid=eid,revision_uuid=uuid.uuid4(),entity_type='medical_visits',entity_uuid=uuid.uuid4(),operation='update',entity_version=1,payload=p,source_clinic_uuid=CLINIC,source_device_uuid=origin,source_generation_uuid=G1,source_sequence=seq,schema_version=1,content_sha256=payload_sha256(p),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0))
try:
 with engine.connect() as c:
  assert c.execute(text('select current_schema()')).scalar()=='public'; assert c.execute(text('select version_num from alembic_version')).scalar()=='20261008_13'; print('identity=head=20261008_13')
 s=Session(engine); service=SyncTransportService(); e1,e2=uuid.uuid4(),uuid.uuid4(); add_change(s,e1,uuid.uuid4(),1001); add_change(s,e2,uuid.uuid4(),2001); s.commit()
 service.publish_committed(s,channel=CH,limit=10,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=B,publisher_generation_uuid=G1)
 with Session(engine) as q:
  pubs=q.scalars(select(SyncEventPublication).where(SyncEventPublication.channel==CH)).all(); print('B_local_publications=',len(pubs)); assert len(pubs)==2
  event=q.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==e1)); assert event
  q.add(SyncRelayAuthorization(carrier_device_uuid=D,origin_device_uuid=event.source_device_uuid,origin_generation_uuid=G1,destination_device_uuid=D,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); q.commit()
  service.publish_relay_event(q,event_uuid=e1,carrier_device_uuid=D,publisher_device_uuid=D,publisher_generation_uuid=G1,destination_device_uuid=D,channel=CH)
 with Session(engine) as q:
  dpub=q.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==e1,SyncEventPublication.publisher_device_uuid==D,SyncEventPublication.publisher_generation_uuid==G1,SyncEventPublication.channel==CH)).all(); print('D_independent_publication=',len(dpub)); assert len(dpub)==1
  # new publisher generation for B gets its own position.
  q.add(SyncRelayAuthorization(carrier_device_uuid=B,origin_device_uuid=q.scalar(select(SyncTransportEvent.source_device_uuid).where(SyncTransportEvent.event_uuid==e2)),origin_generation_uuid=G1,destination_device_uuid=B,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); q.commit()
  service.publish_relay_event(q,event_uuid=e2,carrier_device_uuid=B,publisher_device_uuid=B,publisher_generation_uuid=G2,destination_device_uuid=B,channel=CH)
  q.add(SyncRelayAuthorization(carrier_device_uuid=B,origin_device_uuid=q.scalar(select(SyncTransportEvent.source_device_uuid).where(SyncTransportEvent.event_uuid==e1)),origin_generation_uuid=G1,destination_device_uuid=B,channel=CH,created_at=datetime.now(timezone.utc),is_active=True)); q.commit()
  service.publish_relay_event(q,event_uuid=e1,carrier_device_uuid=B,publisher_device_uuid=B,publisher_generation_uuid=G2,destination_device_uuid=B,channel=CH)
 with Session(engine) as q:
  assert q.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==e1,SyncEventPublication.publisher_device_uuid==B,SyncEventPublication.publisher_generation_uuid==G1,SyncEventPublication.channel==CH))==1
  assert q.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==e1,SyncEventPublication.publisher_device_uuid==B,SyncEventPublication.publisher_generation_uuid==G2,SyncEventPublication.channel==CH))==1; print('new_publisher_generation=independent')
  before=q.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==e1,SyncEventPublication.publisher_device_uuid==B,SyncEventPublication.publisher_generation_uuid==G1,SyncEventPublication.channel==CH)); service.publish_committed(q,channel=CH,limit=10,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=B,publisher_generation_uuid=G1); after=q.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==e1,SyncEventPublication.publisher_device_uuid==B,SyncEventPublication.publisher_generation_uuid==G1,SyncEventPublication.channel==CH)); print('repeat_same_scope=',before,after); assert before==after
 # rollback publication and counter together
 e3=uuid.uuid4(); add_change(q,e3,uuid.uuid4(),3001); q.commit()
 try: service.publish_committed(q,channel=CH,limit=10,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=B,publisher_generation_uuid=G1,_fail_before_commit=True)
 except RuntimeError: pass
 with Session(engine) as fresh:
  assert fresh.scalar(select(SyncEventPublication.id).where(SyncEventPublication.event_uuid==e3)) is None; print('rollback_before_commit=pass')
 print('PASS publication scope, independent publisher/generation, repeat, rollback')
 # Real two-connection concurrency checks.
 ce=uuid.uuid4();
 with Session(engine) as seed:
  add_change(seed,ce,uuid.uuid4(),7001); seed.commit()
 barrier=threading.Barrier(2); outcomes=[]
 def concurrent_publish():
  local=Session(engine)
  try:
   pid=local.execute(text('select pg_backend_pid()')).scalar(); barrier.wait(timeout=10); result=SyncTransportService().publish_committed(local,channel=CH,limit=10,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=B,publisher_generation_uuid=G1); outcomes.append((pid,result))
  except Exception as exc: outcomes.append(type(exc).__name__)
  finally: local.close()
 t1=threading.Thread(target=concurrent_publish); t2=threading.Thread(target=concurrent_publish); t1.start(); t2.start(); t1.join(15); t2.join(15); assert not t1.is_alive() and not t2.is_alive();
 with Session(engine) as fresh:
  same=fresh.scalar(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==ce,SyncEventPublication.publisher_device_uuid==B,SyncEventPublication.publisher_generation_uuid==G1,SyncEventPublication.channel==CH)); pids={x[0] for x in outcomes if isinstance(x,tuple)}; print('concurrent_same_event_pubs=',same,'backend_pids=',sorted(pids),'outcomes=',len(outcomes)); assert same==1 and len(pids)==2 and len(outcomes)==2
 print('PASS concurrent two-connection publication')
 # Case 1: two distinct events, same publisher and a fresh counter.
 ch2='concurrent-'+uuid.uuid4().hex[:8]; o1,o2=uuid.uuid4(),uuid.uuid4(); x1,x2=uuid.uuid4(),uuid.uuid4()
 with Session(engine) as seed:
  add_change(seed,x1,o1,8101); add_change(seed,x2,o2,8102); seed.commit()
 b2=threading.Barrier(2); out2=[]
 def pub_event(origin):
  local=Session(engine)
  try:
   pid=local.execute(text('select pg_backend_pid()')).scalar(); b2.wait(timeout=10); out2.append((pid,SyncTransportService().publish_committed(local,channel=ch2,limit=1,source_device_uuid=origin,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=B,publisher_generation_uuid=G1)))
  except Exception as exc: out2.append(type(exc).__name__)
  finally: local.close()
 t1=threading.Thread(target=pub_event,args=(o1,)); t2=threading.Thread(target=pub_event,args=(o2,)); t1.start(); t2.start(); t1.join(15); t2.join(15)
 with Session(engine) as fresh:
  p2=fresh.scalars(select(SyncEventPublication).where(SyncEventPublication.channel==ch2,SyncEventPublication.publisher_device_uuid==B)).all(); print('two_events_same_publisher=',len(p2),'positions=',sorted(x.publish_sequence for x in p2),'connections=',len({x[0] for x in out2 if isinstance(x,tuple)})); assert len(p2)==2 and len({x.publish_sequence for x in p2})==2 and len(out2)==2
 # Case 2: same event, independent publishers and fresh counters.
 ch3='concurrent-'+uuid.uuid4().hex[:8]; x3=uuid.uuid4(); origin3=uuid.uuid4()
 with Session(engine) as seed: add_change(seed,x3,origin3,8201); seed.commit()
 b3=threading.Barrier(2); out3=[]
 def pub_scope(publisher,generation):
  local=Session(engine)
  try:
   pid=local.execute(text('select pg_backend_pid()')).scalar(); b3.wait(timeout=10); out3.append((pid,SyncTransportService().publish_committed(local,channel=ch3,limit=1,source_device_uuid=origin3,source_generation_uuid=G1,source_clinic_uuid=CLINIC,publisher_device_uuid=publisher,publisher_generation_uuid=generation)))
  except Exception as exc: out3.append(type(exc).__name__)
  finally: local.close()
 t1=threading.Thread(target=pub_scope,args=(B,G1)); t2=threading.Thread(target=pub_scope,args=(D,G1)); t1.start(); t2.start(); t1.join(15); t2.join(15)
 with Session(engine) as fresh:
  p3=fresh.scalars(select(SyncEventPublication).where(SyncEventPublication.event_uuid==x3,SyncEventPublication.channel==ch3)).all(); print('same_event_two_publishers=',len(p3),'publishers=',len({x.publisher_device_uuid for x in p3}),'connections=',len({x[0] for x in out3 if isinstance(x,tuple)}),'outcomes=',out3); assert len(p3)==2 and len({x.publisher_device_uuid for x in p3})==2 and len(out3)==2
 print('PASS remaining publication concurrency cases')
finally:
 try:s.close()
 except Exception:pass



