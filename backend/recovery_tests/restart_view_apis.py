import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]; pids=json.loads((Path(__file__).parent/'view-pids.json').read_text())
for name,pid in pids:
 if name.startswith('api-'):
  try: subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  except Exception: pass
new=[]
for db,port in [('ibn_sina_recovery_test',8811),('ibn_sina_transport_d',8812)]:
 env=os.environ.copy();env['DATABASE_URL']=f'postgresql+psycopg://postgres:admin@127.0.0.1:5432/{db}'
 log=(Path(__file__).parent/f'view-api-{port}.log').open('a')
 p=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(root/'backend'),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP);new.append((f'api-{port}',p.pid))
for item in pids:
 if not item[0].startswith('api-'):new.append(item)
(Path(__file__).parent/'view-pids.json').write_text(json.dumps(new),encoding='utf-8');time.sleep(4);print('restarted APIs')
