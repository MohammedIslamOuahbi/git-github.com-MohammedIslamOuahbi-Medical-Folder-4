import json, os, subprocess, sys, time
from pathlib import Path
import requests
root=Path(__file__).resolve().parents[2]; cred=json.loads((Path(__file__).parent/'.stage4-view-credentials.json').read_text())
procs=[]
for name,db,port in [('recovery_test','ibn_sina_recovery_test',8811),('transport_d','ibn_sina_transport_d',8812)]:
 env=os.environ.copy(); env['DATABASE_URL']=f'postgresql+psycopg://postgres:admin@127.0.0.1:5432/{db}'
 log=(Path(__file__).parent/f'view-api-{port}.log').open('w')
 p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(root/'backend'),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
 procs.append((f'api-{port}',p.pid))
for name,port,api in [('recovery-ui',5171,'http://127.0.0.1:8811/api/v1'),('transport-ui',5172,'http://127.0.0.1:8812/api/v1')]:
 env=os.environ.copy(); env['VITE_API_BASE_URL']=api
 log=(Path(__file__).parent/f'view-ui-{port}.log').open('w')
 p=subprocess.Popen(['npm.cmd','run','dev','--','--host','127.0.0.1','--port',str(port)],cwd=str(root/'frontend'),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
 procs.append((name,p.pid))
(Path(__file__).parent/'view-pids.json').write_text(json.dumps(procs),encoding='utf-8')
time.sleep(4)
for name,db,port in [('recovery_test','ibn_sina_recovery_test',8811),('transport_d','ibn_sina_transport_d',8812)]:
 for role,info in cred[name].items():
  if info['password']:
   r=requests.post(f'http://127.0.0.1:{port}/api/v1/auth/login',json={'email':info['email'],'password':info['password']},timeout=10); assert r.ok, (port,role,r.status_code)
print('Started APIs 8811/8812 and UIs 5171/5172; login checks passed.')
print('PIDs saved in backend/recovery_tests/view-pids.json')
