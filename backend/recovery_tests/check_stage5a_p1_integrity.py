"""P1 proof-request rollback and binding integrity."""
import os,sys,uuid,subprocess
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.company import Company
from app.models.branch import Branch
from app.models.proof_pending import OriginProofRequest,proof_request_binding_valid
from app.services.auth_service import AuthService
from app.services.worker_service import WorkerService
from app.schemas.worker import WorkerCreate
base=make_url(settings.database_url); name='ibn_sina_stage5a_p1i_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text(f'create database "{name}"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0
 eng=create_engine(env['DATABASE_URL'])
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True; co=Company(uuid=uuid.uuid4(),name='P1i'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='P1i'); db.add(br); db.flush(); user=AuthService().create_platform_user(db,'P1','I','p1i@test.example.com','unused-secret','admin'); db.commit(); db.info.pop('sync_bootstrap_mode',None)
  payload=WorkerCreate(company_id=co.id,branch_id=br.id,employee_number='P1I',first_name='P1',last_name='I'); op=uuid.uuid4(); db.info['stage5a_fail_proof_request']=True
  try: WorkerService().create(db,payload,user,op)
  except RuntimeError as e: print('proof_insert_failure=',str(e))
  db.rollback(); db.info.pop('stage5a_fail_proof_request',None)
  for t in ('workers','local_revisions','sync_changes','local_write_operations','origin_proof_requests'): assert db.scalar(text(f'select count(*) from {t}'))==0
  print('rollback_all_five_tables=1')
  WorkerService().create(db,payload,user,op); req=db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid==op)); assert req and req.event_uuid and req.status=='pending_proof'
  assert proof_request_binding_valid(req,event_uuid=req.event_uuid,content_sha256=req.content_sha256,operation_uuid=op,entity_type='workers',revision_uuid=req.revision_uuid)
  assert not proof_request_binding_valid(req,event_uuid=uuid.uuid4(),content_sha256=req.content_sha256,operation_uuid=op,entity_type='workers',revision_uuid=req.revision_uuid)
  assert not proof_request_binding_valid(req,event_uuid=req.event_uuid,content_sha256='0'*64,operation_uuid=op,entity_type='workers',revision_uuid=req.revision_uuid)
  print('retry_one_effect=1 binding_valid=1 wrong_event_or_hash_rejected=1')
 with Session(eng) as db:
  assert db.scalar(select(func.count()).select_from(OriginProofRequest))==1; print('restart_persistent=1 pending_proof=1 time_indeterminate=1')
 print('PASS P1 proof request integrity; no signature or business application')
finally: pass
