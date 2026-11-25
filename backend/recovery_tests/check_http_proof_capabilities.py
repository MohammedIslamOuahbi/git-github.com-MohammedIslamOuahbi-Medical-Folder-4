import os,sys,uuid,subprocess,time,socket
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncRelayAuthorization
from app.services.central_sync_service import CentralSyncService
from app.services.proof_transport_capabilities import worker_proof_transport_decision
BASE=make_url(settings.database_url); root=str(Path(__file__).resolve().parents[1]); names=['ibn_sina_cap_418ef234','ibn_sina_cap_7d4ae3b9']; procs=[]
def port():
 s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
def seed(url,dev,secret):
 e=create_engine(url); h=CentralSyncService()._hash_secret(secret)
 with Session(e) as db: db.add(SyncDevice(uuid=dev,installation_uuid=uuid.uuid4(),device_code='cap-'+dev.hex,device_name='cap-test',registered_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),is_active=True,central_secret_hash=h)); db.commit()
 with Session(e) as db: d=db.scalar(select(SyncDevice).where(SyncDevice.uuid==dev)); assert d and d.is_active and d.central_secret_hash==h; print('fixture_device=',dev,'secret_match=True')
def start(url,p):
 env={**os.environ,'DATABASE_URL':url}
 if 'WORKER_TEST_SERVER_VERSIONS' in os.environ: env['PROOF_TRANSPORT_SUPPORTED_VERSIONS']=os.environ['WORKER_TEST_SERVER_VERSIONS']
 return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(p)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 urls=[BASE.set(database=n).render_as_string(hide_password=False) for n in names];
 for u,n in zip(urls,names):
  e=create_engine(u); print('db=',n,'identity=',e.connect().execute(text('select current_database(),current_schema()')).one(),'head=',e.connect().execute(text('select version_num from alembic_version')).scalar()); q=subprocess.run([sys.executable,'-m','alembic','check'],cwd=root,env={**os.environ,'DATABASE_URL':u},capture_output=True,text=True,timeout=60); print('alembic_check_rc=',q.returncode,'general_schema_debt=users/user_permissions'); cols=e.connect().execute(text("select column_name from information_schema.columns where table_name='proof_transport_capabilities'")).scalars().all(); assert {'connection_scope','proof_transport_version','advertisement_uuid'}.issubset(set(cols))
 devs=[uuid.uuid4(),uuid.uuid4()]; secrets=[uuid.uuid4().hex,uuid.uuid4().hex]
 for u,d,s in zip(urls,devs,secrets): seed(u,d,s)
 ports=[port(),port()]; procs=[start(u,p) for u,p in zip(urls,ports)]
 for p,pr in zip(ports,procs):
  end=time.time()+20
  while time.time()<end:
   if pr.poll() is not None: raise RuntimeError('API_EXIT_'+str(pr.returncode))
   try:
    if requests.get(f'http://127.0.0.1:{p}/openapi.json',timeout=1).status_code==200: break
   except requests.RequestException: pass
   time.sleep(.2)
  else: raise RuntimeError('API_READY_TIMEOUT')
 scope='cap-'+uuid.uuid4().hex[:8]
 # The scope is authorized through the existing relay authorization model;
 # the capability payload is not itself a grant.
 with Session(create_engine(urls[0])) as db:
  origin_device=uuid.uuid4(); origin_generation=uuid.uuid4()
  db.add(SyncRelayAuthorization(
   carrier_device_uuid=devs[0], origin_device_uuid=origin_device,
   origin_generation_uuid=origin_generation, destination_device_uuid=devs[0],
   channel=scope, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
   is_active=True))
  db.commit()
 def post(i,versions,secret=None,peer=None,post_scope=None,origin=None,generation=None):
  h={'X-Sync-Device-UUID':str(devs[i]),'X-Sync-Device-Secret':secret or secrets[i]}
  body={'peer_device_uuid':str(peer or devs[i]),'connection_scope':post_scope or scope,
        'origin_device_uuid':str(origin or origin_device),
        'origin_generation_uuid':str(generation or origin_generation),
        'supported_versions':versions}
  return requests.post(f'http://127.0.0.1:{ports[i]}/api/v1/sync/v2/proof-capabilities',json=body,headers=h,timeout=10)
 from recovery_tests.proof_capability_negotiation import interpret_capability_response
 old_supported=post(0,[1]); print('support_v1=',old_supported.status_code,old_supported.json(),'worker_decision=supported'); assert old_supported.ok
 if os.environ.get('CAPABILITY_ONLY_A') == '1':
  with Session(create_engine(urls[1])) as db:
   db.add(SyncRelayAuthorization(carrier_device_uuid=devs[1], origin_device_uuid=origin_device, origin_generation_uuid=origin_generation, destination_device_uuid=devs[1], channel=scope, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), is_active=True)); db.commit()
  old_supported=post(1,[1],secret=secrets[1],peer=devs[1])
  print('old_supported=',old_supported.status_code,old_supported.json())
  assert old_supported.json()['data']['status']=='accepted'
  assert old_supported.json()['data']['proof_transport_version']==1
  assert old_supported.json()['data']['advertisement_sequence']==1
  procs[1].terminate(); procs[1].wait(timeout=10)
  os.environ['WORKER_TEST_SERVER_VERSIONS']=''
  procs[1]=start(urls[1],ports[1])
  end=time.time()+20
  while time.time()<end:
   if procs[1].poll() is not None: raise RuntimeError('API_DOWNGRADE_EXIT_'+str(procs[1].returncode))
   try:
    if requests.get(f'http://127.0.0.1:{ports[1]}/openapi.json',timeout=1).status_code==200: break
   except requests.RequestException: pass
   time.sleep(.2)
  else: raise RuntimeError('API_DOWNGRADE_READY_TIMEOUT')
  downgraded=post(1,[1],secret=secrets[1],peer=devs[1]); print('downgrade=',downgraded.status_code,downgraded.json()); assert downgraded.json()['data']['status']=='unsupported'
  delayed=interpret_capability_response(old_supported, target=f'http://127.0.0.1:{ports[1]}', peer=devs[1], scope=scope, origin_device=str(origin_device), origin_generation=str(origin_generation), versions=[1], headers={'X-Sync-Device-UUID':str(devs[1]),'X-Sync-Device-Secret':secrets[1]})
  assert delayed=='negotiation_failed'; print('delayed_supported_decision=',delayed,'old_sequence=',old_supported.json()['data']['advertisement_sequence'],'new_sequence=',downgraded.json()['data']['advertisement_sequence'])
  with Session(create_engine(urls[1])) as db:
   row=db.scalar(select(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability).where(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.peer_device_uuid==devs[1], __import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.connection_scope==scope))
   assert row and row.proof_transport_version==0 and row.advertisement_sequence==downgraded.json()['data']['advertisement_sequence']
   print('durable_rows=1 durable_status=unsupported durable_sequence=',row.advertisement_sequence)
  raise SystemExit(0)
 origin2, generation2 = uuid.uuid4(), uuid.uuid4()
 with Session(create_engine(urls[0])) as db:
  db.add(SyncRelayAuthorization(carrier_device_uuid=devs[0], origin_device_uuid=origin2, origin_generation_uuid=generation2, destination_device_uuid=devs[0], channel=scope, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), is_active=True)); db.commit()
 with ThreadPoolExecutor(max_workers=2) as pool:
  concurrent = list(pool.map(lambda args: post(0, [1], origin=args[0], generation=args[1]), [(origin_device, origin_generation), (origin2, generation2)]))
 assert all(x.status_code == 200 for x in concurrent)
 with Session(create_engine(urls[0])) as db:
  rows = db.scalars(select(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability).where(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.peer_device_uuid==devs[0], __import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.connection_scope==scope)).all()
  assert len(rows) == 1 and rows[0].advertisement_sequence >= 3
  print('concurrent_same_row=1 sequence=', rows[0].advertisement_sequence)
 for label,resp in [('unsupported',post(0,[2])),('missing',post(0,[])),('bad_secret',post(0,[1],'wrong')),('spoof',post(0,[1],secrets[0],devs[1]))]: print(label,resp.status_code,resp.json())
 assert post(0,[1]).ok; r=post(0,[2]); assert r.json()['data']['status']=='unsupported'; print('worker_decision=unsupported');
 old_data=old_supported.json()['data']; delayed=interpret_capability_response(old_supported, target=f'http://127.0.0.1:{ports[0]}', peer=devs[0], scope=scope, origin_device=str(origin_device), origin_generation=str(origin_generation), versions=[1], headers={'X-Sync-Device-UUID':str(devs[0]),'X-Sync-Device-Secret':secrets[0]})
 assert delayed=='negotiation_failed'; print('delayed_supported_decision=negotiation_failed old_sequence=',old_data['advertisement_sequence'],'new_sequence=',r.json()['data']['advertisement_sequence'])
 with Session(create_engine(urls[0])) as db: count=db.scalar(select(func.count()).select_from(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability).where(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.peer_device_uuid==devs[0])); assert count==1; print('durable_rows=',count)
 before_scope_rows=count
 unauthorized_scope='unauthorized-'+uuid.uuid4().hex[:8]
 body={'peer_device_uuid':str(devs[0]),'connection_scope':unauthorized_scope,'origin_device_uuid':str(origin_device),'origin_generation_uuid':str(origin_generation),'supported_versions':[1]}
 h={'X-Sync-Device-UUID':str(devs[0]),'X-Sync-Device-Secret':secrets[0]}
 r=requests.post(f'http://127.0.0.1:{ports[0]}/api/v1/sync/v2/proof-capabilities',json=body,headers=h,timeout=10)
 print('unauthorized_scope=',r.status_code,r.json())
 assert r.status_code==403
 with Session(create_engine(urls[0])) as db:
  after_scope_rows=db.scalar(select(func.count()).select_from(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability).where(__import__('app.models.proof_transport_capability',fromlist=['ProofTransportCapability']).ProofTransportCapability.peer_device_uuid==devs[0]))
  assert after_scope_rows==before_scope_rows
 procs[0].terminate(); procs[0].wait(timeout=10); procs[0]=start(urls[0],ports[0])
 end=time.time()+20
 while time.time()<end:
  if procs[0].poll() is not None: raise RuntimeError('API_RESTART_EXIT_'+str(procs[0].returncode))
  try:
   if requests.get(f'http://127.0.0.1:{ports[0]}/openapi.json',timeout=1).status_code==200: break
  except requests.RequestException: pass
  time.sleep(.2)
 else: raise RuntimeError('API_RESTART_READY_TIMEOUT')
 r=post(0,[1]); print('restart=',r.status_code); assert r.ok
 with Session(create_engine(urls[0])) as db: d=db.scalar(select(SyncDevice).where(SyncDevice.uuid==devs[0])); d.is_revoked=True; d.is_active=False; db.commit()
 r=post(0,[1]); print('revoked=',r.status_code); assert r.status_code in (401,403)
finally:
 for p in procs:
  if p and p.poll() is None: p.terminate(); p.wait(timeout=10)





