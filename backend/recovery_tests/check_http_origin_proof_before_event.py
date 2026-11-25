"""Proof-before-event HTTP test; reconciliation never applies business data."""
import os, sys, time, uuid, requests
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.origin_proof import OriginProof
from app.models.sync_change import SyncChange
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.models.sync_transport import SyncTransportEvent
from app.services.origin_proof_reconciliation import reconcile_origin_proof
from recovery_tests.check_http_origin_proof_transport import head, port, prepare_origin_proof_fixture, start

ROOT=Path(__file__).resolve().parents[1]
def main():
 s=os.environ['STAGE5_SOURCE_DB']; t=os.environ['STAGE5_TARGET_DB']; ps=[]
 try:
  print('source_database=',head(s),'target_database=',head(t),'head=20261008_27')
  f=prepare_origin_proof_fixture(s,t,include_target_event=False); sp,tp=port(),port(); ps=[start(s,sp),start(t,tp)]
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   try:
    if requests.get(f'http://127.0.0.1:{sp}/openapi.json',timeout=1).ok and requests.get(f'http://127.0.0.1:{tp}/openapi.json',timeout=1).ok: break
   except requests.RequestException: pass
   time.sleep(.2)
  with Session(create_engine(s)) as db:
   proof=db.scalar(select(OriginProof).where(OriginProof.proof_uuid==f.proof_uuid)); change=db.scalar(select(SyncChange).where(SyncChange.change_uuid==f.event))
   proof_payload={**proof.proof,'signature':proof.proof['signature']}; event_payload={'event_uuid':str(f.event),'source_sequence':1,'source_clinic_uuid':str(f.clinic),'source_device_uuid':str(f.src_dev),'schema_version':1,'entity_type':change.entity_type,'entity_uuid':str(change.entity_uuid),'revision_uuid':str(change.revision_uuid),'operation':change.operation,'payload':change.payload,'content_sha256':change.content_sha256,'publish_sequence':1,'publication_channel':f.channel,'publication_source_device_uuid':str(f.src_dev),'publication_source_generation_uuid':str(f.gen)}
  headers={'X-Sync-Device-UUID':str(f.dst_dev),'X-Sync-Device-Secret':f.dst_secret}
  body={'contract_version':'2.1','proof_uuid':str(f.proof_uuid),'event_uuid':str(f.event),'content_sha256':change.content_sha256,'source_device_uuid':str(f.src_dev),'source_generation_uuid':str(f.gen),'source_clinic_uuid':str(f.clinic),'channel':f.channel,'proof':proof_payload}
  r=requests.post(f'http://127.0.0.1:{tp}/api/v1/sync/v2/proof-receive',json=body,headers=headers,timeout=10); print('proof_receive=',r.status_code)
  with Session(create_engine(t)) as db: assert reconcile_origin_proof(db,event_uuid=f.event,peer_device_uuid=f.dst_dev)['status']=='pending_event'; print('before_event=pending_event')
  event_body={'contract_version':'2.1','source_clinic_uuid':str(f.clinic),'source_device_uuid':str(f.src_dev),'source_generation_uuid':str(f.gen),'channel':f.channel,'events':[event_payload],'limit':100,'publisher_device_uuid':str(f.src_dev),'publisher_generation_uuid':str(f.gen),'publisher_clinic_uuid':str(f.clinic)}
  r=requests.post(f'http://127.0.0.1:{tp}/api/v1/sync/v2/receive',json=event_body,headers=headers,timeout=10); print('event_receive=',r.status_code, r.text[:500])
  with Session(create_engine(t)) as db:
   result=reconcile_origin_proof(db,event_uuid=f.event,peer_device_uuid=f.dst_dev); print('reconcile=',result['status'],result['reason'],'verification=',result.get('verification')); assert result['status']=='rejected' and result['reason']=='TIME_INDETERMINATE'; assert db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid==f.event)) is not None
   assert len(db.scalars(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==f.event)).all())==1; print('business_application=0 receipt_count=1')
 finally:
  for p in ps:
   if p.poll() is None: p.terminate(); p.wait(timeout=10)
if __name__=='__main__': main()
