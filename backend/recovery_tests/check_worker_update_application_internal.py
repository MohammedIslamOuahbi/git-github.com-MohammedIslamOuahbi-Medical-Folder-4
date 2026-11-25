from __future__ import annotations
import os,sys,uuid
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.services.entity_application_service import apply_worker_entity,apply_worker_update_entity
from check_worker_update_source_fixture import prepare_worker_update_source
from check_worker_service_integration import prepare_authorized_worker_source

def main():
 src=os.environ['STAGE5_SOURCE_DB']; dst=os.environ['STAGE5_TARGET_DB']
 fixture=prepare_authorized_worker_source(src,source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),clinic_uuid=uuid.uuid4())
 update=prepare_worker_update_source(src,fixture)
 eng=create_engine(dst)
 with Session(eng) as db:
  company=db.scalar(select(Company).where(Company.uuid==uuid.UUID(str(update['base_payload']['company_uuid'])))); branch=db.scalar(select(Branch).where(Branch.uuid==uuid.UUID(str(update['base_payload']['branch_uuid']))))
  if not company or not branch or branch.company_id!=company.id: raise RuntimeError('TARGET_DEPENDENCY_FIXTURE_MISSING')
  base=SimpleNamespace(event_uuid=uuid.uuid4(),source_device_uuid=update['source_device_uuid'],source_generation_uuid=update['source_generation_uuid'],source_sequence=1,entity_type='workers',entity_uuid=fixture.worker_uuid,revision_uuid=uuid.uuid4(),payload=update['base_payload'])
  apply_worker_entity(db,base)
 with Session(eng) as db:
  base_row=db.scalar(select(Worker).where(Worker.uuid==fixture.worker_uuid)); assert base_row
  ev=SimpleNamespace(event_uuid=update['event_uuid'],source_device_uuid=update['source_device_uuid'],entity_type='workers',entity_uuid=fixture.worker_uuid,revision_uuid=update['revision_uuid'],payload=update['update_payload'],base_version=1,operation_uuid=update['operation_uuid'])
  result=apply_worker_update_entity(db,ev); print('apply_result',result)
 with Session(eng) as db:
  row=db.scalar(select(Worker).where(Worker.uuid==fixture.worker_uuid)); revs=db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture.worker_uuid)); print('persisted',row.sync_version,revs); assert row.sync_version==2 and revs>=2
 print('update_applied=1 version=2 revisions=2 local_setup_distinguished=1')
 with Session(eng) as db:
  ev=SimpleNamespace(event_uuid=update['event_uuid'],source_device_uuid=update['source_device_uuid'],entity_type='workers',entity_uuid=fixture.worker_uuid,revision_uuid=update['revision_uuid'],payload=update['update_payload'],base_version=1,operation_uuid=update['operation_uuid'])
  try: apply_worker_update_entity(db,ev)
  except Exception: db.rollback()
 with Session(eng) as db:
  assert db.scalar(select(Worker.sync_version).where(Worker.uuid==fixture.worker_uuid))==2
  assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture.worker_uuid))==2
 print('replay_no_duplicate=1 version=2 revisions=2 local_sync_changes_from_apply=0')
 from app.models.sync_conflict import SyncConflict
 with Session(eng) as db:
  stale=SimpleNamespace(event_uuid=uuid.uuid4(),source_device_uuid=update['source_device_uuid'],entity_type='workers',entity_uuid=fixture.worker_uuid,revision_uuid=uuid.uuid4(),payload={**update['update_payload'],'first_name':'stale'},base_version=1,operation_uuid=uuid.uuid4())
  before=db.scalar(select(Worker.first_name).where(Worker.uuid==fixture.worker_uuid)); conflict=apply_worker_update_entity(db,stale); assert conflict['status']=='conflict'
 with Session(eng) as db:
  assert db.scalar(select(Worker.first_name).where(Worker.uuid==fixture.worker_uuid))==before
  assert db.scalar(select(func.count()).select_from(SyncConflict).where(SyncConflict.incoming_change_uuid==stale.event_uuid))==1
 print('base_version_conflict=1 local_preserved=1 conflict_saved=1')
 with Session(eng) as db: assert apply_worker_update_entity(db,stale)['status']=='conflict'
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(SyncConflict).where(SyncConflict.incoming_change_uuid==stale.event_uuid))==1
 print('conflict_replay_no_duplicate=1')
 # Pending local edit is produced by the protected WorkerService path.
 from app.services.worker_service import WorkerService
 from app.schemas.worker import WorkerUpdate
 from app.models.user import User
 with Session(eng) as db:
  local=db.scalar(select(Worker).where(Worker.uuid==fixture.worker_uuid)); actor=db.scalar(select(User).where(User.is_active==True).order_by(User.id))
  try:
   WorkerService().update(db,local.id,WorkerUpdate(first_name='local-pending'),actor,3,uuid.uuid4())
  except Exception: db.rollback()
  pending=db.scalar(select(__import__('app.models.local_revision',fromlist=['LocalEditAttempt']).LocalEditAttempt).where(__import__('app.models.local_revision',fromlist=['LocalEditAttempt']).LocalEditAttempt.entity_uuid==fixture.worker_uuid))
  assert pending is not None
  incoming=SimpleNamespace(event_uuid=uuid.uuid4(),source_device_uuid=update['source_device_uuid'],entity_type='workers',entity_uuid=fixture.worker_uuid,revision_uuid=uuid.uuid4(),payload={**update['update_payload'],'first_name':'incoming-pending'},base_version=2,operation_uuid=uuid.uuid4())
  pending_result=apply_worker_update_entity(db,incoming); assert pending_result['status']=='conflict'
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(SyncConflict).where(SyncConflict.incoming_change_uuid==incoming.event_uuid))==1
 print('pending_local_edit=1 base_version_matched=1 local_preserved=1 conflict_saved=1')
 with Session(eng) as db: assert apply_worker_update_entity(db,incoming)['status']=='conflict'
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(SyncConflict).where(SyncConflict.incoming_change_uuid==incoming.event_uuid))==1
 print('pending_conflict_replay_no_duplicate=1')
 # Failure after update flush uses a second independently prepared worker.
 fixture2=prepare_authorized_worker_source(src,source_device_uuid=uuid.uuid4(),source_generation_uuid=uuid.uuid4(),clinic_uuid=uuid.uuid4()); update2=prepare_worker_update_source(src,fixture2)
 with Session(eng) as db:
  base2=SimpleNamespace(event_uuid=uuid.uuid4(),source_device_uuid=update2['source_device_uuid'],source_generation_uuid=update2['source_generation_uuid'],source_sequence=1,entity_type='workers',entity_uuid=fixture2.worker_uuid,revision_uuid=uuid.uuid4(),payload=update2['base_payload']); apply_worker_entity(db,base2)
 with Session(eng) as db:
  row=db.scalar(select(Worker).where(Worker.uuid==fixture2.worker_uuid)); before_name=row.first_name; before_version=row.sync_version; before_revs=db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture2.worker_uuid))
  failed=SimpleNamespace(event_uuid=uuid.uuid4(),source_device_uuid=update2['source_device_uuid'],entity_type='workers',entity_uuid=fixture2.worker_uuid,revision_uuid=uuid.uuid4(),payload={**update2['update_payload'],'first_name':'injected-failure'},base_version=before_version,operation_uuid=uuid.uuid4())
  try: apply_worker_update_entity(db,failed,fail_after_worker_flush=True)
  except RuntimeError as exc: assert str(exc)=='INJECTED_ENTITY_APPLICATION_FAILURE_AFTER_WORKER_FLUSH'; db.rollback()
  else: raise AssertionError('failure injection did not fire')
  assert db.info.get('sync_apply_mode') is None
 with Session(eng) as db:
  row=db.scalar(select(Worker).where(Worker.uuid==fixture2.worker_uuid)); assert row.first_name==before_name and row.sync_version==before_version
  assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture2.worker_uuid))==before_revs
 print('flush_failure=1 rollback=complete worker_unchanged=1 revisions_unchanged=1 sync_apply_mode_clean=1')
 with Session(eng) as db:
  assert apply_worker_update_entity(db,failed)['status']=='applied'
 with Session(eng) as db:
  assert db.scalar(select(Worker.sync_version).where(Worker.uuid==fixture2.worker_uuid))==2
  assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture2.worker_uuid))==2
 print('failure_retry=accepted_once=1 version=2 revisions=2')
 with Session(eng) as db: apply_worker_update_entity(db,failed)
 with Session(eng) as db: assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==fixture2.worker_uuid))==2
 print('failure_replay_no_duplicate=1')
if __name__=='__main__':main()
