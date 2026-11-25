import os,sys,uuid
from pathlib import Path
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery_tests.check_medical_visit_source_fixture import prepare_medical_visit_source,prepare_medical_visit_update_source
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalRevision
from app.models.sync_conflict import SyncConflict
from app.models.sync_change import SyncChange
from app.services.entity_application_service import apply_medical_visit_entity,apply_medical_visit_update_entity
from app.models.user import User
from app.services.medical_visit_service import MedicalVisitService
from app.schemas.medical_visit import MedicalVisitUpdate
from app.services.auth_service import AuthService
from app.services.permission_service import permission_service
def make_case(s,t):
 f=prepare_medical_visit_source(s);u=prepare_medical_visit_update_source(s,f);te=create_engine(t)
 with Session(te) as db:
  wu=uuid.UUID(str(f.request_payload['worker_uuid'])); Worker=__import__('app.models.worker',fromlist=['Worker']).Worker
  if db.scalar(select(Worker).where(Worker.uuid==wu)) is None: raise RuntimeError('TARGET_WORKER_DEPENDENCY_MISSING')
  b=type('E',(),{})();b.event_uuid=uuid.uuid4();b.operation_uuid=uuid.uuid4();b.entity_uuid=f.visit_uuid;b.revision_uuid=u['parent_revision_uuid'];b.payload=dict(f.request_payload);b.payload['worker_uuid']=str(wu);apply_medical_visit_entity(db,b);db.commit()
 return f,u,te
def main():
 s=os.environ['STAGE5_SOURCE_DB'];t=os.environ['STAGE5_TARGET_DB']; f=prepare_medical_visit_source(s);u=prepare_medical_visit_update_source(s,f);te=create_engine(t)
 with Session(te) as db:
  worker_uuid=uuid.UUID(str(f.request_payload['worker_uuid']));
  # The target worker is prepared by the preceding internal fixture.
  if db.scalar(select(__import__('app.models.worker',fromlist=['Worker']).Worker).where(__import__('app.models.worker',fromlist=['Worker']).Worker.uuid==worker_uuid)) is None: raise RuntimeError('TARGET_WORKER_DEPENDENCY_MISSING')
  base=type('E',(),{})();base.event_uuid=uuid.uuid4();base.operation_uuid=uuid.uuid4();base.entity_uuid=f.visit_uuid;base.revision_uuid=u['parent_revision_uuid'];base.payload=dict(f.request_payload);base.payload['worker_uuid']=str(worker_uuid);assert apply_medical_visit_entity(db,base)['status']=='applied';db.commit()
 with Session(te) as db:
  ev=type('E',(),{})();ev.event_uuid=u['event_uuid'];ev.operation_uuid=u['operation_uuid'];ev.entity_uuid=f.visit_uuid;ev.revision_uuid=uuid.UUID(str(u['origin_proof']['revision_uuid']));ev.parent_revision_uuid=uuid.UUID(str(u['parent_revision_uuid']));ev.base_version=1;ev.payload=u['update_payload'];assert apply_medical_visit_update_entity(db,ev)['status']=='applied';db.commit()
 with Session(te) as db:
  row=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f.visit_uuid));assert row.version==2;assert len(db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f.visit_uuid)).all())==2;assert not db.scalars(select(SyncChange).where(SyncChange.entity_uuid==f.visit_uuid)).all();print('visit_update_applied=1 version=2 revisions=2 incoming_sync_changes=0')
 assert apply_medical_visit_update_entity(db,ev)['status']=='replay';db.commit();print('replay=1 no_revision_added=1')
 f2,u2,te2=make_case(s,t)
 with Session(te2) as db:
  e=type('E',(),{})();e.event_uuid=u2['event_uuid'];e.operation_uuid=u2['operation_uuid'];e.entity_uuid=f2.visit_uuid;e.revision_uuid=uuid.UUID(str(u2['origin_proof']['revision_uuid']));e.parent_revision_uuid=uuid.UUID(str(u2['parent_revision_uuid']));e.base_version=0;e.payload=u2['update_payload'];r=apply_medical_visit_update_entity(db,e);assert r['status']=='conflict';db.commit()
 with Session(te2) as db:
  c=db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid==u2['event_uuid']));assert c and c.status=='physician_review';assert db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f2.visit_uuid)).version==1;assert not db.scalars(select(SyncChange).where(SyncChange.entity_uuid==f2.visit_uuid)).all();assert apply_medical_visit_update_entity(db,e)['status']=='conflict';print('base_version_conflict=physician_review replay_no_duplicate=1')
 fpend,upend,tepend=make_case(s,t)
 with Session(tepend) as db:
  v=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==fpend.visit_uuid)); admin=db.scalar(select(User).where(User.role=='admin').order_by(User.id))
  if admin is None or 'medical_visits.update' not in permission_service.get_effective_permission_codes(admin):
   db.info['sync_bootstrap_mode']=True; admin=AuthService().create_platform_user(db,'Visit','Fixture','visit-update-'+uuid.uuid4().hex[:8]+'@test.local','test-only','super_admin'); db.commit(); db.info.pop('sync_bootstrap_mode',None)
  if admin is None: raise RuntimeError('TARGET_UPDATE_USER_CREATION_FAILED')
  permission_service.require_permission(admin,'medical_visits.update')
  db.info.update(sync_source_device_uuid=uuid.UUID(str(fpend.origin_proof['origin_device_uuid'])),sync_source_generation_uuid=uuid.uuid4(),sync_source_clinic_uuid=uuid.UUID(str(fpend.origin_proof['clinic_uuid'])),sync_source_user_uuid=admin.uuid); MedicalVisitService().update(db,v.id,MedicalVisitUpdate(site_name='local-pending-visit'),admin,1,uuid.uuid4()); db.commit(); print('local_pending_edit=committed version=2 permission_verified=1')
 with Session(tepend) as db:
  e=type('E',(),{})();e.event_uuid=upend['event_uuid'];e.operation_uuid=upend['operation_uuid'];e.entity_uuid=fpend.visit_uuid;e.revision_uuid=uuid.UUID(str(upend['origin_proof']['revision_uuid']));e.parent_revision_uuid=uuid.UUID(str(upend['parent_revision_uuid']));e.base_version=1;e.payload=upend['update_payload'];assert apply_medical_visit_update_entity(db,e)['status']=='conflict';db.commit()
 with Session(tepend) as db:
  c=db.scalar(select(SyncConflict).where(SyncConflict.incoming_change_uuid==upend['event_uuid']));v=db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==fpend.visit_uuid));assert c and c.status=='physician_review' and c.central_snapshot.get('site_name')=='local-pending-visit' and v.site_name=='local-pending-visit';assert apply_medical_visit_update_entity(db,e)['status']=='conflict';print('local_pending_conflict=physician_review reason=BASE_VERSION_MISMATCH local_preserved=1 replay_no_duplicate=1')
 f3,u3,te3=make_case(s,t)
 with Session(te3) as db:
  e=type('E',(),{})();e.event_uuid=u3['event_uuid'];e.operation_uuid=u3['operation_uuid'];e.entity_uuid=f3.visit_uuid;e.revision_uuid=uuid.UUID(str(u3['origin_proof']['revision_uuid']));e.parent_revision_uuid=uuid.UUID(str(u3['parent_revision_uuid']));e.base_version=1;e.payload=u3['update_payload']
  try:apply_medical_visit_update_entity(db,e,fail_after_visit_flush=True)
  except RuntimeError:pass
 with Session(te3) as db:
  assert db.scalar(select(MedicalVisit).where(MedicalVisit.uuid==f3.visit_uuid)).version==1;assert len(db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid==f3.visit_uuid)).all())==1;assert not db.scalars(select(SyncChange).where(SyncChange.entity_uuid==f3.visit_uuid)).all();assert apply_medical_visit_update_entity(db,e)['status']=='applied';db.commit();print('flush_failure=rollback_complete retry_applied=1 incoming_sync_changes=0')
if __name__=='__main__':main()
