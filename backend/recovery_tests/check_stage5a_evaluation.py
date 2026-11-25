"""5A isolated evaluation ledger test; never applies business rows."""
import os,sys,uuid,subprocess
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationDecision,SyncApplicationAttempt
from app.services.sync_application_evaluation_service import evaluate_event
base=make_url(settings.database_url); run=uuid.uuid4().hex[:8]; name='ibn_sina_stage5a_'+run; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); root=str(Path(__file__).resolve().parents[1]); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}
try:
 with admin.connect() as c:
  ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text('create database "'+name+'"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); print('migration_exit=',p.returncode); print(p.stderr[-2000:]); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL']); eid=uuid.uuid4(); entity=uuid.uuid4(); now=datetime.now(timezone.utc)
 with Session(eng) as db:
  db.add(SyncTransportEvent(event_uuid=eid,source_clinic_uuid=uuid.uuid4(),source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),source_sequence=1,entity_type='workers',entity_uuid=entity,revision_uuid=None,parent_revision_uuid=None,operation='create',schema_version=1,content_sha256='a'*64,payload={'employee_number':'fixture-1','first_name':'Fixture','last_name':'Worker'},origin_kind='inbox',created_at=now)); db.commit()
  d1=evaluate_event(db,eid); first_decision=d1.decision; first_reason=d1.reason_code; d2=evaluate_event(db,eid); assert first_decision=='blocked_authorization_evidence' and first_reason=='AUTHORIZATION_EVIDENCE_MISSING' and d2.id==d1.id
  assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid==eid))==1
  d3=evaluate_event(db,eid,authorization_evidence={'reference':'fixture-grant-1'}); assert d3.decision=='blocked_authorization_evidence' and d3.reason_code=='AUTHORIZATION_EVIDENCE_MISSING'
  assert db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid==eid))==2
  print('decisions=',first_decision,d3.decision,'reason=',first_reason,'fixture_evidence_not_authoritative=1','attempts=2','business_application=0')
 with eng.connect() as c:
  assert c.execute(text('select version_num from alembic_version')).scalar()=='20261008_16'; print('head=20261008_16 persistence=ok')
 print('PASS stage5A evaluation ledger; no business tables changed')
finally: pass
