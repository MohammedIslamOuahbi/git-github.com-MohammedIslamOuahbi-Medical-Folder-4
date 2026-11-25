"""P1 worker create process restart; proof request only."""
import os,sys,uuid,subprocess
from pathlib import Path
from sqlalchemy import create_engine,text,select
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.user import User
from app.models.proof_pending import OriginProofRequest
from app.services.auth_service import AuthService
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
if os.getenv('P1_WORKER_CHILD'):
 eng=create_engine(os.environ['P1_DB']);
 with Session(eng) as db:
  user=db.scalar(select(User).where(User.email=='p1restart@test.example.com')); p=WorkerCreate(company_id=int(os.environ['P1_COMPANY']),branch_id=int(os.environ['P1_BRANCH']),employee_number='P1-RESTART',first_name='Restart',last_name='Worker'); WorkerService().create(db,p,user,uuid.UUID(os.environ['P1_OP'])); req=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==uuid.UUID(os.environ['P1_OP']))); print(f'pid={os.getpid()} request={req.request_uuid} event={req.event_uuid} status={req.status} time={req.time_state}')
 raise SystemExit(0)
base=make_url(settings.database_url); name='ibn_sina_p1_restart_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL'])
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True; co=Company(uuid=uuid.uuid4(),name='P1 restart'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='P1 restart'); db.add(br); db.flush(); AuthService().create_platform_user(db,'P1','Restart','p1restart@test.example.com','unused-secret','admin'); db.commit(); db.info.pop('sync_bootstrap_mode',None); company_id,branch_id=co.id,br.id
 op=uuid.uuid4(); child={**env,'P1_WORKER_CHILD':'1','P1_DB':env['DATABASE_URL'],'P1_COMPANY':str(company_id),'P1_BRANCH':str(branch_id),'P1_OP':str(op)}
 first=subprocess.run([sys.executable,__file__],cwd=root,env=child,capture_output=True,text=True,timeout=60); second=subprocess.run([sys.executable,__file__],cwd=root,env=child,capture_output=True,text=True,timeout=60); assert first.returncode==0 and second.returncode==0; print('process1=',first.stdout.strip()); print('process2=',second.stdout.strip())
 with Session(eng) as db:
  req=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==op)); assert req and req.status=='pending_proof' and req.time_state=='time_indeterminate'; print('fresh_session=one_request_original_links=1 no_new_uuid=1 signature=0')
 print('PASS P1 worker process restart')
finally: pass
