import os,sys,subprocess,time,uuid,socket,requests
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.branch import Branch
from app.services.auth_service import AuthService
from app.core.security import hash_password

BASE=make_url(settings.database_url); DB=BASE.set(database='ibn_sina_cap_418ef234').render_as_string(hide_password=False); ROOT=str(Path(__file__).resolve().parents[1]); proc=None
email=os.environ.get('PREVIEW_EMAIL','babzizsaleh@ibnsina.com'); password=os.environ.get('PREVIEW_PASSWORD','babziz saleh')
op=str(uuid.uuid4())
try:
 with Session(create_engine(DB)) as db:
  db.info['sync_bootstrap_mode']=True
  user=AuthService().create_platform_user(db,'Preview','Operator',email,password,'admin')
  company=Company(name='Synthetic Preview Company '+uuid.uuid4().hex[:6]); db.add(company); db.flush()
  branch=Branch(company_id=company.id,name='Synthetic Branch'); db.add(branch); db.commit(); company_id,branch_id=company.id,branch.id
 s=socket.socket(); s.bind(('127.0.0.1',0)); port=s.getsockname()[1]; s.close()
 env={**os.environ,'DATABASE_URL':DB}; log_path=Path(__file__).with_name('.preview-api.log'); log_handle=open(log_path,'w',encoding='utf-8'); proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log_handle,stderr=log_handle)
 end=time.time()+20
 while time.time()<end:
  try:
   if requests.get(f'http://127.0.0.1:{port}/openapi.json',timeout=1).status_code==200: break
  except Exception: pass
  time.sleep(.2)
 else: raise RuntimeError('API_READY_TIMEOUT')
 base=f'http://127.0.0.1:{port}'; r=requests.post(base+'/api/v1/auth/login',json={'email':email,'password':password},timeout=10); assert r.status_code==200; token=r.json()['data']['access_token']; h={'Authorization':'Bearer '+token}
 me=requests.get(base+'/api/v1/auth/me',headers=h); print('me=',me.status_code,me.json()); assert me.status_code==200
 for account_email, account_password in [('babzizsaleh@ibnsina.com','babziz saleh'),('babzizmostafa@ibnsina.com','babziz mostafa'),('ouahbimohammedislam@ibnsina.com','mohammed islam')]:
  login_check=requests.post(base+'/api/v1/auth/login',json={'email':account_email,'password':account_password},timeout=10)
  assert login_check.status_code==200
 print('account_logins=3 passed')
 worker={'company_id':company_id,'branch_id':branch_id,'employee_number':'PREVIEW-'+uuid.uuid4().hex[:8],'first_name':'Synthetic','last_name':'Worker','national_id':'SYN-'+uuid.uuid4().hex[:10],'birth_date':'1990-01-01','gender':'other','etat_actual':'present','is_active':True}
 r=requests.post(base+'/api/v1/workers',json=worker,headers={**h,'X-Operation-UUID':op},timeout=10); print('login=200 worker=',r.status_code); assert r.status_code in (200,201); wid=r.json()['data']['id']
 r=requests.post(base+'/api/v1/medical-visits',json={'worker_id':wid,'visit_date':'2026-10-14','status':'draft','form_data':{'synthetic':True}},headers={**h,'X-Operation-UUID':str(uuid.uuid4())},timeout=10); print('visit=',r.status_code); assert r.status_code in (200,201); vid=r.json()['data']['id']
 pdf=requests.get(base+f'/api/v1/medical-visits/{vid}/pdf',headers=h); Path(__file__).with_name('preview-smoke-visit.pdf').write_bytes(pdf.content)
 print('worker_get=',requests.get(base+f'/api/v1/workers/{wid}',headers=h).status_code,'visit_get=',requests.get(base+f'/api/v1/medical-visits/{vid}',headers=h).status_code,'pdf=',pdf.status_code)
 assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
 try:
  from pypdf import PdfReader
  reader=PdfReader(str(Path(__file__).with_name('preview-smoke-visit.pdf')))
  text_content='\n'.join(page.extract_text() or '' for page in reader.pages)
  print('pdf_text_preview=',repr(text_content[:500]))
  assert 'Worker' in text_content
  print('pdf_check=passed text=True pages=',len(reader.pages))
 except ImportError:
  print('pdf_check=header_only pypdf_not_installed')
 assert requests.get(base+f'/api/v1/workers/{wid}',headers=h).status_code==200
 proc.terminate(); proc.wait(timeout=10)
 proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log_handle,stderr=log_handle)
 end=time.time()+20
 while time.time()<end:
  try:
   if requests.get(base+'/openapi.json',timeout=1).status_code==200: break
  except Exception: pass
  time.sleep(.2)
 else: raise RuntimeError('API_RESTART_READY_TIMEOUT')
 print('after_restart=',requests.get(base+f'/api/v1/workers/{wid}',headers=h).status_code,requests.get(base+f'/api/v1/medical-visits/{vid}',headers=h).status_code,requests.get(base+f'/api/v1/medical-visits/{vid}/pdf',headers=h).status_code)
 assert requests.get(base+f'/api/v1/workers/{wid}',headers=h).status_code==200
 assert requests.get(base+f'/api/v1/medical-visits/{vid}',headers=h).status_code==200
 assert requests.get(base+f'/api/v1/medical-visits/{vid}/pdf',headers=h).status_code==200
finally:
 if proc and proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
 try: log_handle.close()
 except Exception: pass
