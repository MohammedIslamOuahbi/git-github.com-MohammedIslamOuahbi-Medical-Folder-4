import os,sys,uuid,subprocess
from pathlib import Path
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
base=make_url(settings.database_url); name='ibn_sina_worker_rollback_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
def counts(db):
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Worker,LocalRevision,SyncChange,LocalWriteOperation))
try:
    with admin.connect() as c: c.execute(text('create database "'+name+'"'))
    p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0,p.stderr[-1000:]
    eng=create_engine(env['DATABASE_URL']); user=SimpleNamespace(uuid=uuid.uuid4(),id=None,role='doctor',is_active=True)
    with Session(eng) as db:
        db.info['sync_bootstrap_mode']=True
        try:
            co=Company(uuid=uuid.uuid4(),name='rollback fixture'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='rollback branch'); db.add(br); db.commit(); company_id,branch_id=co.id,br.id
        finally: db.info.pop('sync_bootstrap_mode',None)
    with Session(eng) as db: baseline=counts(db); print('baseline=',baseline)
    def sql_case(label,needle):
        op=uuid.uuid4(); payload=WorkerCreate(company_id=company_id,branch_id=branch_id,employee_number=label+'-'+uuid.uuid4().hex,first_name='Rollback',last_name=label)
        def hook(conn,cursor,statement,parameters,context,executemany):
            if needle.lower() in statement.lower(): raise RuntimeError('synthetic_'+label)
        event.listen(eng,'before_cursor_execute',hook)
        try:
            with Session(eng) as db:
                try: WorkerService().create(db,payload,user,op)
                except RuntimeError as exc: assert str(exc)=='synthetic_'+label
                else: raise AssertionError(label+' injection did not fire')
        finally: event.remove(eng,'before_cursor_execute',hook)
        with Session(eng) as db: assert counts(db)==baseline; print(label,'rollback=',counts(db),'hook_removed=1')
        with Session(eng) as db: result=WorkerService().create(db,payload,user,op); db.commit()
        with Session(eng) as db: assert counts(db)==tuple(x+1 for x in baseline); print(label,'retry=one_complete_effect',result.uuid)
        return tuple(x+1 for x in baseline)
    baseline=sql_case('revision','local_revisions')
    baseline=sql_case('syncchange','sync_changes')
    op=uuid.uuid4(); payload=WorkerCreate(company_id=company_id,branch_id=branch_id,employee_number='commit-'+uuid.uuid4().hex,first_name='Rollback',last_name='commit'); original=Session.commit
    def fail_commit(self): raise RuntimeError('synthetic_commit')
    Session.commit=fail_commit
    try:
        with Session(eng) as db:
            try: WorkerService().create(db,payload,user,op)
            except RuntimeError as exc: assert str(exc)=='synthetic_commit'; db.rollback()
            else: raise AssertionError('commit injection did not fire')
    finally: Session.commit=original
    with Session(eng) as db: assert counts(db)==baseline; print('before_commit rollback=',counts(db),'bootstrap_leaked=0')
    with Session(eng) as db: result=WorkerService().create(db,payload,user,op); db.commit()
    with Session(eng) as db: assert counts(db)==tuple(x+1 for x in baseline); print('before_commit retry=one_complete_effect',result.uuid,'persistent=1')
    print('PASS worker create rollback points; no medical application')
finally: pass
