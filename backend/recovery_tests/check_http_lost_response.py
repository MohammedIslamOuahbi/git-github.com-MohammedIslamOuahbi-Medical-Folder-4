"""HTTP 2.1 lost-response test for receive and ACK."""
import os,sys,uuid,time,threading,subprocess,socket
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
import requests
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.models.sync_device import SyncDevice
from app.models.sync_change import SyncChange
from app.models.sync_transport import SyncEventInbox,SyncEventDelivery,SyncRelayAuthorization
from app.services.central_sync_service import CentralSyncService
from app.services.sync_journal import payload_sha256
from app.services.sync_transport_service import SyncTransportService
BASE=make_url(settings.database_url);A='ibn_sina_recovery_test';C='ibn_sina_transport_c_4a2d1164';PA=8971;PC=8972
RUN=uuid.uuid4().hex[:8];EVENT,ENTITY,REV,ORIGIN,OGEN,CLINIC,PUB,PGEN,PEER=[uuid.uuid4() for _ in range(9)];CH='lost-'+RUN;SECRET='stage4-'+RUN;PROCS=[]
def eng(db):return create_engine(BASE.set(database=db),pool_pre_ping=True)
def url(db):return BASE.set(database=db).render_as_string(hide_password=False)
def stop(p):
    if p and p.poll() is None:p.terminate();p.wait(5)
def start(db,port):return subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=str(ROOT),env={**os.environ,'DATABASE_URL':url(db)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait(port):
    end=time.time()+30
    while time.time()<end:
        try:
            with socket.create_connection(('127.0.0.1',port),.3):return
        except OSError:time.sleep(.2)
    raise TimeoutError('api_not_ready')
class Cut(BaseHTTPRequestHandler):
    target=''
    last_status=None
    def do_POST(self):
        b=self.rfile.read(int(self.headers.get('Content-Length','0')));h={k:v for k,v in self.headers.items() if k.lower()!='host'};r=requests.post(self.target+self.path,data=b,headers=h,timeout=15);Cut.last_status=r.status_code;self.close_connection=True
    def log_message(self,*a):pass
def cut(target,port):
    Cut.target=target;s=HTTPServer(('127.0.0.1',port),Cut);t=threading.Thread(target=s.handle_request,daemon=True);t.start();return s,t
def show(label,r):
    code=None
    try:
        j=r.json();d=j.get('detail',{});code=(d.get('details') or {}).get('error_code') if isinstance(d,dict) else None
    except ValueError:j=None
    print(label,'status=',r.status_code,'content_type=',r.headers.get('content-type','').split(';')[0],'error_code=',code);return j
try:
    for db in (A,C):
        with eng(db).connect() as q:
            ident=q.execute(text('select current_database(),current_schema(),inet_server_port()')).one();head=q.execute(text('select version_num from alembic_version')).scalar_one();print('identity',ident[0],ident[1],ident[2],'head',head);assert ident[0]==db and head=='20261008_15'
    h=CentralSyncService()._hash_secret(SECRET);payload={'synthetic_lost_response':RUN}
    with Session(eng(A)) as s:
        for u in (PEER,ORIGIN):s.add(SyncDevice(uuid=u,installation_uuid=uuid.uuid4(),device_code='lost-'+u.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=ORIGIN,origin_generation_uuid=OGEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True));s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=PUB,origin_generation_uuid=PGEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True))
        s.add(SyncChange(change_uuid=EVENT,revision_uuid=REV,entity_type='synthetic_transport',entity_uuid=ENTITY,operation='update',entity_version=1,payload=payload,source_clinic_uuid=CLINIC,source_device_uuid=ORIGIN,source_generation_uuid=OGEN,source_sequence=1,schema_version=1,content_sha256=payload_sha256(payload),occurred_at=datetime.now(timezone.utc),central_status='never_submitted',retry_count=0));s.commit();svc=SyncTransportService();svc.publish_committed(s,channel=CH,source_device_uuid=ORIGIN,source_generation_uuid=OGEN,source_clinic_uuid=CLINIC,publisher_device_uuid=PUB,publisher_generation_uuid=PGEN);svc.queue_for_peer(s,peer_device_uuid=PEER,channel=CH,source_clinic_uuid=CLINIC,source_generation_uuid=OGEN,source_device_uuid=ORIGIN,limit=10)
    with Session(eng(C)) as s:
        for u in (PEER,ORIGIN):s.add(SyncDevice(uuid=u,installation_uuid=uuid.uuid4(),device_code='lost-c-'+u.hex[:8],device_name='synthetic',registered_at=datetime.now(timezone.utc),is_active=True,central_secret_hash=h))
        s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=ORIGIN,origin_generation_uuid=OGEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True));s.add(SyncRelayAuthorization(carrier_device_uuid=PEER,origin_device_uuid=PUB,origin_generation_uuid=PGEN,destination_device_uuid=PEER,channel=CH,created_at=datetime.now(timezone.utc),is_active=True));s.commit()
    PROCS[:]=[start(A,PA),start(C,PC)];wait(PA);wait(PC);H={'X-Sync-Device-UUID':str(PEER),'X-Sync-Device-Secret':SECRET};pull={'contract_version':'2.1','source_clinic_uuid':str(CLINIC),'source_device_uuid':str(ORIGIN),'source_generation_uuid':str(OGEN),'channel':CH,'limit':10,'after_sequence':0,'publisher_device_uuid':str(PUB),'publisher_generation_uuid':str(PGEN),'publisher_clinic_uuid':str(CLINIC)}
    bad=dict(pull);bad['publisher_device_uuid']=str(uuid.uuid4());bad['publisher_generation_uuid']=str(uuid.uuid4())
    with eng(A).connect() as q: before=q.execute(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT)).scalar_one()
    br=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=bad,headers=H,timeout=10);show('pull_unauthorized_publisher',br);assert br.status_code in (401,403,409)
    with eng(A).connect() as q: assert q.execute(select(func.count()).select_from(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT)).scalar_one()==before
    pr=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/pull',json=pull,headers=H,timeout=10);j=show('pull',pr);assert pr.ok and j and j.get('data') and any(e['event_uuid']==str(EVENT) for e in j['data']['events']);ev=next(e for e in j['data']['events'] if e['event_uuid']==str(EVENT));body={**pull,'events':[ev]}
    s,t=cut(f'http://127.0.0.1:{PC}',8973)
    try:
        try:requests.post('http://127.0.0.1:8973/api/v1/sync/v2/receive',json=body,headers=H,timeout=10)
        except requests.RequestException:pass
    finally:t.join(15);s.server_close()
    print('receive_cut_upstream_status=',Cut.last_status)
    with Session(eng(C)) as q:assert q.scalar(select(func.count()).select_from(SyncEventInbox).where(SyncEventInbox.event_uuid==EVENT))==1;print('receive_commit inbox=1')
    assert requests.post(f'http://127.0.0.1:{PC}/api/v1/sync/v2/receive',json=body,headers=H,timeout=10).ok
    ack={'contract_version':'2.1','event_uuid':str(EVENT),'channel':CH,'lease_token':ev['lease_token'],'publisher_device_uuid':str(PUB),'publisher_generation_uuid':str(PGEN),'publisher_clinic_uuid':str(CLINIC)};s,t=cut(f'http://127.0.0.1:{PA}',8974)
    try:
        try:requests.post('http://127.0.0.1:8974/api/v1/sync/v2/ack',json=ack,headers=H,timeout=10)
        except requests.RequestException:pass
    finally:t.join(15);s.server_close()
    with Session(eng(A)) as q:d=q.scalar(select(SyncEventDelivery).where(SyncEventDelivery.event_uuid==EVENT,SyncEventDelivery.publisher_generation_uuid==PGEN));print('ack_commit status=',d.status if d else None);assert d and d.status=='delivered'
    ar=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/ack',json=ack,headers=H,timeout=10);show('ack_retry',ar);assert ar.ok
    bad=dict(ack);bad['lease_token']=str(uuid.uuid4());br=requests.post(f'http://127.0.0.1:{PA}/api/v1/sync/v2/ack',json=bad,headers=H,timeout=10);show('ack_wrong_token',br);assert br.status_code in (409,422,403)
    print('PASS lost receive and ACK responses; durable/idempotent retries; wrong token rejected')
finally:
    for p in PROCS:stop(p)
