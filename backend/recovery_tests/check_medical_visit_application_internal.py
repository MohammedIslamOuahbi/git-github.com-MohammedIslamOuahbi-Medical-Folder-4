import os,sys,uuid
from pathlib import Path
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recovery_tests.check_medical_visit_source_fixture import prepare_medical_visit_source
from app.models.worker import Worker
from app.models.company import Company
from app.models.branch import Branch
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.services.entity_application_service import apply_worker_entity,apply_medical_visit_entity
def head(u):
 with create_engine(u).connect() as c:return c.execute(text('select version_num from alembic_version')).scalar()
def main():
 s=os.environ.get('STAGE5_SOURCE_DB');t=os.environ.get('STAGE5_TARGET_DB')
 if not s or not t or s==t:raise RuntimeError('ISOLATED_SOURCE_TARGET_REQUIRED')
 if head(s)!=head(t):raise RuntimeError('SOURCE_TARGET_HEAD_MISMATCH')
 f=prepare_medical_visit_source(s);se,te=create_engine(s),create_engine(t)
 with Session(se) as db:
  sw=db.scalar(select(Worker).where(Worker.uuid==uuid.UUID(str(f.request_payload['worker_uuid']))))
  if sw is None:raise RuntimeError('SOURCE_WORKER_MISSING')
  comp=db.get(Company,sw.company_id);branch=db.get(Branch,sw.branch_id)
  wp={k:getattr(sw,k) for k in ('employee_number','first_name','last_name','gender','etat_actual','is_active')};wp.update(company_uuid=str(comp.uuid) if comp else '',branch_uuid=str(branch.uuid) if branch else '');wu=sw.uuid
 with Session(te) as db:
  if db.scalar(select(Worker).where(Worker.uuid==wu)) is None:
   if not wp['company_uuid'] or not wp['branch_uuid'] or not db.scalar(select(Company).where(Company.uuid==uuid.UUID(wp['company_uuid']))) or not db.scalar(select(Branch).where(Branch.uuid==uuid.UUID(wp['branch_uuid']))):raise RuntimeError('TARGET_WORKER_DEPENDENCIES_MISSING')
   e=type('E',(),{})();e.entity_uuid=wu;e.event_uuid=uuid.uuid4();e.operation_uuid=uuid.uuid4();e.revision_uuid=uuid.uuid4();e.source_sequence=1;e.entity_type='workers';e.source_device_uuid=uuid.uuid4();e.payload=wp;apply_worker_entity(db,e)
  db.commit()
 def ev(eid,op,rid,entity=None):
  e=type('E',(),{})();e.event_uuid=eid;e.operation_uuid=op;e.entity_uuid=entity or f.visit_uuid;e.revision_uuid=rid;e.payload=dict(f.request_payload);e.payload['worker_uuid']=str(wu);return e
 with Session(te) as db:
  assert db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f.visit_uuid)) is None
  e=ev(f.event_uuid,f.operation_uuid,uuid.uuid4());assert apply_medical_visit_entity(db,e)['status']=='applied';db.commit()
 with Session(te) as db:
  row=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f.visit_uuid));revs=db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f.visit_uuid)).all();assert row and row.worker_id and len(revs)==1 and not db.scalars(select(SyncChange).where(SyncChange.entity_uuid==f.visit_uuid)).all();assert apply_medical_visit_entity(db,ev(f.event_uuid,f.operation_uuid,revs[0].revision_uuid))['status']=='replay';db.commit();print('target_visit_applied=1 replay_same_visit=1 revision_count=1 incoming_sync_changes=0')
 failed,op=uuid.uuid4(),uuid.uuid4()
 with Session(te) as db:
  try:apply_medical_visit_entity(db,ev(uuid.uuid4(),op,uuid.uuid4(),failed),fail_after_visit_flush=True)
  except RuntimeError as x:assert str(x)=='INJECTED_VISIT_APPLICATION_FAILURE_AFTER_FLUSH'
 with Session(te) as db:
  assert not db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==failed)) and not db.scalar(select(LocalRevision).where(LocalRevision.entity_uuid==failed)) and not db.scalar(select(LocalWriteOperation).where(LocalWriteOperation.operation_uuid==op));assert apply_medical_visit_entity(db,ev(uuid.uuid4(),op,uuid.uuid4(),failed))['status']=='applied';db.commit();print('flush_failure=rollback_complete retry_after_rollback=1 sync_apply_mode_clean=1')
if __name__=='__main__':main()
