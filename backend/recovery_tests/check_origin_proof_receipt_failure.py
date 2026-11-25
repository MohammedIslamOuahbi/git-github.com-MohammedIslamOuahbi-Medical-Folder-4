"""Focused receipt-mismatch test using shared fixture."""
import os, subprocess, sys, time
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.origin_proof_delivery import OriginProofDelivery
from app.models.origin_proof_transport import OriginProofTransportReceipt
from recovery_tests.check_http_origin_proof_transport import head, port, prepare_origin_proof_fixture, start
ROOT=Path(__file__).resolve().parents[1]
def wait_api(ps,ports):
 import requests
 deadline=time.monotonic()+20
 while time.monotonic()<deadline and all(p.poll() is None for p in ps):
  try:
   if all(requests.get(f'http://127.0.0.1:{x}/openapi.json',timeout=1).status_code==200 for x in ports): return
  except requests.RequestException: pass
  time.sleep(.2)
 raise RuntimeError('API_READY_TIMEOUT')
def env_for(f,s,t,mutate):
 e={**os.environ,'DATABASE_URL':f.source,'PROOF_TRANSPORT_ENABLED':'1','WORKER_PEER':str(f.dst_dev),'WORKER_CHANNEL':f.channel,'WORKER_TARGET':f'http://127.0.0.1:{t}','WORKER_SOURCE':f'http://127.0.0.1:{s}','WORKER_SECRET':f.dst_secret,'WORKER_ORIGIN_DEVICE':str(f.src_dev),'WORKER_ORIGIN_GENERATION':str(f.gen),'WORKER_PUBLISHER_DEVICE':str(f.src_dev),'WORKER_PUBLISHER_GENERATION':str(f.gen),'WORKER_PUBLISHER_CLINIC':str(f.clinic),'WORKER_CONNECTION_SCOPE':f.channel,'WORKER_CAPABILITY_TARGET':f'http://127.0.0.1:{t}','WORKER_CAPABILITY_VERSIONS':'[1]','WORKER_CYCLES':'1','WORKER_LEASE_SECONDS':'2','PROOF_DELIVERY_LEASE_SECONDS':'2'}
 if mutate: e['PROOF_TEST_MUTATE_RECEIPT']='1'
 else: e.pop('PROOF_TEST_MUTATE_RECEIPT',None)
 for k in ('PROOF_AFTER_CLAIM_PAUSE_FILE','PROOF_AFTER_CLAIM_RELEASE_FILE','PROOF_AFTER_RECEIVE_PAUSE_FILE','PROOF_AFTER_RECEIVE_RELEASE_FILE','PROOF_TEST_FAIL_ACK'): e.pop(k,None)
 return e
def worker(e):
 p=subprocess.Popen([sys.executable,'recovery_tests/_run_http_worker.py'],cwd=ROOT,env=e,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 out,_=p.communicate(timeout=40); return p.returncode,out
def main():
 s=os.environ['STAGE5_SOURCE_DB']; t=os.environ['STAGE5_TARGET_DB']; ps=[]
 try:
  print('source_database=',head(s),'target_database=',head(t),'head=20261008_27'); f=prepare_origin_proof_fixture(s,t); print('fixture_ready=1')
  sp,tp=port(),port(); ps=[start(s,sp),start(t,tp)]; wait_api(ps,(sp,tp)); print('api_pids=',ps[0].pid,ps[1].pid)
  rc,out=worker(env_for(f,sp,tp,True)); print(out,end=''); assert rc!=0; print('receipt_mismatch_rejected=1 worker_rc=',rc)
  with Session(create_engine(s)) as db:
   d=db.scalar(select(OriginProofDelivery).where(OriginProofDelivery.proof_uuid==f.proof_uuid)); assert d.status!='delivered' and d.delivered_at is None; print('before_resume_source_delivered=0')
  with Session(create_engine(t)) as db:
   rs=db.scalars(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==f.event)).all(); assert len(rs)==1; rid=rs[0].receipt_uuid; print('before_resume_target_receipts=1 ack_not_sent=1')
  time.sleep(3); rc,out=worker(env_for(f,sp,tp,False)); print(out,end=''); assert rc==0
  with Session(create_engine(s)) as db:
   d=db.scalar(select(OriginProofDelivery).where(OriginProofDelivery.proof_uuid==f.proof_uuid)); assert d.status=='delivered' and d.delivered_at is not None; print('after_resume_source_delivery=delivered')
  with Session(create_engine(t)) as db:
   rs=db.scalars(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==f.event)).all(); assert len(rs)==1 and rs[0].receipt_uuid==rid; print('after_resume_target_receipts=1 receipt_uuid_stable=1')
 finally:
  for p in ps:
   if p.poll() is None: p.terminate(); p.wait(timeout=10)
if __name__=='__main__': main()
