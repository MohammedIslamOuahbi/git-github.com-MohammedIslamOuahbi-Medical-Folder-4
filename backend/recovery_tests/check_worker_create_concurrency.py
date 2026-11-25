"""Concurrent protected worker-create contract check; no medical application."""
import os,sys,uuid,subprocess,threading
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.models.proof_pending import OriginProofRequest
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
from types import SimpleNamespace
base=make_url(settings.database_url); name='ibn_sina_worker_concurrent_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
def counts(db): return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Worker,LocalRevision,SyncChange,LocalWriteOperation,OriginProofRequest))
def run_pair(engine,payload_a,payload_b,op,user_a,user_b):
    gate=threading.Barrier(2); results=[]; errors=[]
    def one(payload,user):
        try:
            with Session(engine) as db:
                pid=db.scalar(text('select pg_backend_pid()')); gate.wait(timeout=15); value=WorkerService().create(db,payload,user,op); results.append((pid,'accepted',str(value.uuid)))
        except Exception as exc: results.append((None,'rejected',type(exc).__name__+':'+str(getattr(exc,'detail',str(exc)))))
    ts=[threading.Thread(target=one,args=(payload_a,user_a)),threading.Thread(target=one,args=(payload_b,user_b))]
    [t.start() for t in ts]; [t.join(30) for t in ts]; assert all(not t.is_alive() for t in ts); return results
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text('create database "'+name+'"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0,p.stderr[-1000:]
 eng=create_engine(env['DATABASE_URL']); user=SimpleNamespace(uuid=uuid.uuid4(),id=None,role='doctor',is_active=True)
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True
  try:
   co=Company(uuid=uuid.uuid4(),name='concurrent fixture'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='concurrent branch'); db.add(br); db.commit()
  finally: db.info.pop('sync_bootstrap_mode',None)
  payload=WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='concurrent-'+uuid.uuid4().hex,first_name='Concurrent',last_name='Worker'); op=uuid.uuid4(); before=counts(db)
 r1=run_pair(eng,payload,payload,op,user,user); print('same_operation_results=',r1)
 with Session(eng) as db:
  final=counts(db); assert final==(before[0]+1,before[1]+1,before[2]+1,before[3]+1,before[4]+1); rows=db.scalars(select(Worker).where(Worker.employee_number==payload.employee_number)).all(); assert len(rows)==1; proof=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==op)); change=db.scalar(select(SyncChange).where(SyncChange.operation_uuid==op)); rev=db.scalar(select(LocalRevision).where(LocalRevision.revision_uuid==proof.revision_uuid)); assert proof.event_uuid==change.change_uuid and proof.content_sha256==change.content_sha256 and proof.revision_uuid==change.revision_uuid and proof.origin_user_uuid==change.source_user_uuid; print('same_operation_persistent=',final,'backend_pids=',sorted(str(x[0]) for x in r1 if x[0]),'proof_event_matches_change=1 proof_revision_hash_origin=1')
 op2=uuid.uuid4(); other=WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='conflict-'+uuid.uuid4().hex,first_name='Different',last_name='Content'); r2=run_pair(eng,payload,other,op2,user,user); print('conflicting_reuse_results=',r2)
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(Worker))==2
  assert db.scalar(select(func.count()).select_from(LocalRevision))==2 and db.scalar(select(func.count()).select_from(SyncChange))==2 and db.scalar(select(func.count()).select_from(LocalWriteOperation))==2
  assert db.scalar(select(func.count()).select_from(OriginProofRequest))==2
  print('conflicting_reuse_no_partial_effect=1; one_winner_only=1; no_extra_proof_request=1')
 print('PASS concurrent protected worker create; journal auto-registration; no medical application')
finally: pass
