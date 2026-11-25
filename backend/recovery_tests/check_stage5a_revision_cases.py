"""5A structural/revision cases; fixture writes happen before the evaluation baseline."""
import os,sys,uuid,subprocess
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationDecision,SyncApplicationAttempt
from app.services.sync_application_evaluation_service import evaluate_event
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
from app.schemas.worker import WorkerUpdate
from types import SimpleNamespace
from app.services.sync_journal import register_sync_journal
from app.services.local_revision_baseline import baseline_batch
base=make_url(settings.database_url); name='ibn_sina_stage5a_rev_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1]); now=datetime.now(timezone.utc)
payload={'employee_number':'fixture','first_name':'Fixture','last_name':'Worker'}; results=[]
def add_event(db, eid, target, op='update', parent=None, rev=None, digest='a'*64):
    db.add(SyncTransportEvent(event_uuid=eid,source_clinic_uuid=uuid.uuid4(),source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),source_sequence=1,entity_type='workers',entity_uuid=target,revision_uuid=rev,parent_revision_uuid=parent,operation=op,schema_version=1,content_sha256=digest,payload=payload,origin_kind='inbox',created_at=datetime.now(timezone.utc))); db.flush()
try:
 with admin.connect() as c: c.execute(text('create database "'+name+'"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0,p.stderr[-1000:]
 eng=create_engine(env['DATABASE_URL'])
 register_sync_journal()
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True
  co1=Company(uuid=uuid.uuid4(),name='5A Co 1'); co2=Company(uuid=uuid.uuid4(),name='5A Co 2'); db.add_all([co1,co2]); db.flush(); br1=Branch(uuid=uuid.uuid4(),company_id=co1.id,name='5A B1'); br2=Branch(uuid=uuid.uuid4(),company_id=co2.id,name='5A B2'); db.add_all([br1,br2]); db.commit()
  user=SimpleNamespace(uuid=uuid.uuid4(),id=None,role='doctor',is_active=True)
  db.info.pop('sync_bootstrap_mode', None)
  w1=WorkerService().create(db,WorkerCreate(company_id=co1.id,branch_id=br1.id,employee_number='5A-1',first_name='One',last_name='Worker'),user,uuid.uuid4()); db.commit()
  w2=WorkerService().create(db,WorkerCreate(company_id=co2.id,branch_id=br2.id,employee_number='5A-2',first_name='Two',last_name='Worker'),user,uuid.uuid4()); db.commit()
  w1=db.get(Worker,w1.id); w2=db.get(Worker,w2.id)
  if db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==w2.uuid)) == 0:
   WorkerService().update(db,w2.id,WorkerUpdate(first_name='Two-Updated'),user,1,uuid.uuid4()); db.commit(); w2=db.get(Worker,w2.id)
  # Baseline is now produced by the real protected write/journal path; do not
  # add revisions here to hide a missing write-side revision.
  WorkerService().update(db,w1.id,WorkerUpdate(first_name='One-Updated'),user,1,uuid.uuid4()); db.commit(); w1=db.get(Worker,w1.id)
  revs1=db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==w1.uuid).order_by(LocalRevision.local_version)).all(); revs2=db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==w2.uuid).order_by(LocalRevision.local_version)).all(); print('protected_write_versions=',w1.sync_version,w2.sync_version,'revisions=',len(revs1),len(revs2)); assert revs1 and revs2
  base1,cur1,base2=revs1[0].revision_uuid,revs1[-1].revision_uuid,revs2[-1].revision_uuid
  def snapshot(tag):
   tables=['workers','local_revisions','local_write_operations','sync_changes','sync_transport_events','sync_event_inbox','sync_event_deliveries','sync_publication_receipts','sync_transport_cursors']
   vals={t:db.scalar(text(f'SELECT count(*) FROM {t}')) for t in tables}
   print(tag, vals)
   return vals
  baseline=snapshot('A fixture_after_protected_writes')
  cases=[('update_parent_matches',w1.uuid,'update',cur1,None,'a'*64),('parent_missing',w1.uuid,'update',uuid.uuid4(),None,'a'*64),('parent_absent',w1.uuid,'update',None,None,'a'*64),('parent_other_entity',w1.uuid,'update',base2,None,'a'*64),('competing_branch',w1.uuid,'update',base1,uuid.uuid4(),'a'*64),('known_duplicate',w1.uuid,'update',cur1,cur1,'a'*64),('revision_content_mismatch',w1.uuid,'update',cur1,cur1,'b'*64),('create_existing',w1.uuid,'create',None,None,'c'*64),('update_target_missing',uuid.uuid4(),'update',uuid.uuid4(),None,'d'*64)]
  event_ids=[]
  for label,target,op,parent,rev,digest in cases:
   eid=uuid.uuid4(); event_ids.append(eid); add_event(db,eid,target,op,parent,rev,digest)
  db.commit(); middle=snapshot('B events_before_evaluation')
  for label,eid in zip([x[0] for x in cases],event_ids):
   d=evaluate_event(db,eid); attempts=db.scalar(select(func.count()).select_from(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid==eid)); results.append((label,d.decision,d.reason_code,attempts));
  after=snapshot('C after_evaluation_commit')
  assert baseline['workers']==middle['workers']==after['workers'] and baseline['local_revisions']==middle['local_revisions']==after['local_revisions']
  assert baseline['sync_changes']==middle['sync_changes']==after['sync_changes']
  assert middle['sync_transport_events']==baseline['sync_transport_events']+len(cases)
 for row in results: print('case=',row)
 assert all(x[1] != 'applied' and x[1] != 'ready_for_application' for x in results)
 print('PASS stage5A revision cases; business baseline unchanged')
finally: pass
