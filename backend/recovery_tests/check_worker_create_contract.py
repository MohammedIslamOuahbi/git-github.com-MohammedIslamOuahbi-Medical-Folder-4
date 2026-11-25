"""Isolated contract check for the protected WorkerService.create path."""
import os,sys,uuid,subprocess
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,text,select,func,event
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
from types import SimpleNamespace
base=make_url(settings.database_url); name='ibn_sina_worker_contract_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text('create database "'+name+'"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0,p.stderr[-1000:]
 eng=create_engine(env['DATABASE_URL']); user=SimpleNamespace(uuid=uuid.uuid4(),id=None,role='doctor',is_active=True)
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True; co=Company(uuid=uuid.uuid4(),name='contract fixture'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='contract branch'); db.add(br); db.commit(); db.info.pop('sync_bootstrap_mode',None)
  op=uuid.uuid4(); payload=WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='contract-'+uuid.uuid4().hex,first_name='Contract',last_name='Worker'); result=WorkerService().create(db,payload,user,op); wid=result.uuid; db.commit()
  row=db.scalar(select(Worker).where(Worker.uuid==wid)); rev=db.scalar(select(LocalRevision).where(LocalRevision.entity_uuid==wid)); change=db.scalar(select(SyncChange).where(SyncChange.entity_uuid==wid)); operation=db.get(LocalWriteOperation,op); assert row and rev and change and operation
  assert rev.operation_uuid==op and change.operation_uuid==op and change.revision_uuid==rev.revision_uuid and operation.result_payload['uuid']==str(wid)
  before=(db.scalar(select(func.count()).select_from(Worker)),db.scalar(select(func.count()).select_from(LocalRevision)),db.scalar(select(func.count()).select_from(SyncChange)))
  replay=WorkerService().create(db,payload,user,op); assert replay.uuid==wid; db.commit(); after=(db.scalar(select(func.count()).select_from(Worker)),db.scalar(select(func.count()).select_from(LocalRevision)),db.scalar(select(func.count()).select_from(SyncChange))); assert before==after
  try: WorkerService().create(db,WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='different',first_name='Different',last_name='Worker'),user,op)
  except Exception: db.rollback()
  else: raise AssertionError('operation UUID content reuse accepted')
  other=SimpleNamespace(uuid=uuid.uuid4(),id=None,role='doctor',is_active=True)
  try: WorkerService().create(db,payload,other,op)
  except Exception: db.rollback()
  else: raise AssertionError('operation UUID actor reuse accepted')
  print('create=worker+revision+change+operation; retry=no_extra_effect; conflicting_reuse=rejected; counts=',after)
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(Worker))==1 and db.scalar(select(func.count()).select_from(LocalRevision))==1 and db.scalar(select(func.count()).select_from(SyncChange))==1; print('fresh_session=persistent; no_duplicate_listener_event=1')
 # rollback injection: fail before commit after the service has staged worker/revision/change.
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True; co=db.scalar(select(Company)); br=db.scalar(select(Branch)); db.info.pop('sync_bootstrap_mode',None); op=uuid.uuid4(); payload=WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='rollback-'+uuid.uuid4().hex,first_name='Rollback',last_name='Worker')
  original=db.commit
  def fail_commit(): raise RuntimeError('synthetic_before_commit')
  db.commit=fail_commit
  try: WorkerService().create(db,payload,user,op)
  except RuntimeError as exc: assert str(exc)=='synthetic_before_commit'; db.rollback()
  finally: db.commit=original
  assert db.scalar(select(func.count()).select_from(Worker))==1 and db.scalar(select(func.count()).select_from(LocalRevision))==1 and db.scalar(select(func.count()).select_from(SyncChange))==1; print('rollback_before_commit=worker_revision_change_operation_rolled_back')
 print('PASS worker create contract; barriers remain active; medical application=0')
finally: pass
