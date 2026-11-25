"""Real FastAPI contract check for worker creation on an isolated DB."""
import os,sys,uuid,time,socket,subprocess,requests,tempfile
from pathlib import Path
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.branch import Branch
from app.models.worker import Worker
from app.models.local_revision import LocalRevision,LocalWriteOperation
from app.models.sync_change import SyncChange
from app.services.auth_service import AuthService
base=make_url(settings.database_url); name='ibn_sina_http_worker_'+uuid.uuid4().hex[:8]; admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT'); env={**os.environ,'DATABASE_URL':base.set(database=name).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1]); proc=None; api_log=None
try:
 with admin.connect() as c: ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text('create database "'+name+'"'))
 p=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,capture_output=True,text=True,timeout=180); assert p.returncode==0,p.stderr[-1000:]
 eng=create_engine(env['DATABASE_URL']); admin_pw='HttpAdmin-'+uuid.uuid4().hex; assistant_pw='HttpAssistant-'+uuid.uuid4().hex; admin2_pw='HttpAdmin2-'+uuid.uuid4().hex
 with Session(eng) as db:
  db.info['sync_bootstrap_mode']=True
  try:
   co=Company(uuid=uuid.uuid4(),name='http fixture'); db.add(co); db.flush(); br=Branch(uuid=uuid.uuid4(),company_id=co.id,name='http branch'); db.add(br); db.flush(); auth=AuthService(); admin_u=auth.create_platform_user(db,'HTTP','Admin','http-admin@test.example.com',admin_pw,'admin'); admin2=auth.create_platform_user(db,'HTTP','Admin2','http-admin2@test.example.com',admin2_pw,'admin'); assistant=auth.create_platform_user(db,'HTTP','Doctor','http-doctor@test.example.com',assistant_pw,'doctor'); db.commit(); company_id,branch_id=co.id,br.id
  finally: db.info.pop('sync_bootstrap_mode',None)
 sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close(); api_log=tempfile.NamedTemporaryFile(prefix='http-worker-api-',suffix='.log',delete=False); proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=api_log,stderr=subprocess.STDOUT)
 end=time.time()+30
 while time.time()<end:
  if proc.poll() is not None: raise RuntimeError('api_exited')
  try:
   with socket.create_connection(('127.0.0.1',port),.2): break
  except OSError: time.sleep(.1)
 url=f'http://127.0.0.1:{port}/api/v1/workers'; payload={'company_id':company_id,'branch_id':branch_id,'employee_number':'HTTP-'+uuid.uuid4().hex,'first_name':'HTTP','last_name':'Worker'}; op=str(uuid.uuid4())
 r=requests.post(url,json=payload,timeout=20); print('unauthenticated=',r.status_code); assert r.status_code in {401,403}
 def token(email,pw):
  x=requests.post(f'http://127.0.0.1:{port}/api/v1/auth/login',json={'email':email,'password':pw},timeout=20); assert x.status_code==200; return {'Authorization':'Bearer '+x.json()['data']['access_token']}
 ah=token('http-admin@test.example.com',admin_pw); ah2=token('http-admin2@test.example.com',admin2_pw); sh=token('http-doctor@test.example.com',assistant_pw)
 for label,headers in [('admin',ah),('admin2',ah2),('assistant',sh)]:
  me=requests.get(f'http://127.0.0.1:{port}/api/v1/auth/me',headers=headers,timeout=20); print('auth_me_'+label+'=',me.status_code); assert me.status_code==200
 r=requests.post(url,json=payload,headers={**sh,'X-Operation-UUID':str(uuid.uuid4())},timeout=20); print('insufficient_role=',r.status_code); assert r.status_code in {401,403}
 invalid_payload=requests.post(url,json={**payload,"last_name":None},headers={**ah,'X-Operation-UUID':str(uuid.uuid4())},timeout=20); print('invalid_payload=',invalid_payload.status_code); assert invalid_payload.status_code in {400,422}
 missing_operation=requests.post(url,json=payload,headers=ah,timeout=20); print('missing_operation_uuid=',missing_operation.status_code); assert missing_operation.status_code in {400,422}
 bad=requests.post(url,json=payload,headers={**ah,'X-Operation-UUID':'bad'},timeout=20); print('invalid_operation_uuid=',bad.status_code); assert bad.status_code in {400,422}
 good=requests.post(url,json=payload,headers={**ah,'X-Operation-UUID':op},timeout=20); print('valid=',good.status_code); assert good.status_code==201; data=good.json()['data']; repeat=requests.post(url,json=payload,headers={**ah,'X-Operation-UUID':op},timeout=20); print('repeat=',repeat.status_code); assert repeat.status_code==201 and repeat.json()['data']['uuid']==data['uuid']
 changed=requests.post(url,json={**payload,"first_name":"Different"},headers={**ah,'X-Operation-UUID':op},timeout=20); print('same_operation_changed_payload=',changed.status_code); assert changed.status_code in {400,409,422}
 other=requests.post(url,json=payload,headers={**ah2,'X-Operation-UUID':op},timeout=20); print('same_operation_other_authorized_user=',other.status_code); assert other.status_code in {400,409,422}
 with Session(eng) as db:
  wid=uuid.UUID(data['uuid']); assert db.scalar(select(func.count()).select_from(Worker).where(Worker.uuid==wid))==1; assert db.scalar(select(func.count()).select_from(LocalRevision).where(LocalRevision.entity_uuid==wid))==1; assert db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid==wid))==1; assert db.scalar(select(func.count()).select_from(LocalWriteOperation).where(LocalWriteOperation.operation_uuid==uuid.UUID(op)))==1; print('persistent=worker1 revision1 change1 operation1')
 print('PASS HTTP worker create contract; no incoming application')
finally:
 if proc is not None and proc.poll() is None: proc.terminate()
 if api_log is not None: api_log.close()
