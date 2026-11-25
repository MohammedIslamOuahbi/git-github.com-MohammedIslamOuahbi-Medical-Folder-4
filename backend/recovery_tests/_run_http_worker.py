import os,sys,uuid,requests,time,json
from threading import Lock
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.sync_transport_worker import SyncTransportWorker
import app.services.sync_transport_service as transport_service
worker_id=os.environ.get('WORKER_ID','unknown')
_capability_lock = Lock()
_latest_capability_sequence = {}
status_file=os.environ.get('WORKER_STATUS_FILE')
def after_application_business_commit(row):
 pause=os.environ.get('WORKER_AFTER_BUSINESS_COMMIT_FILE')
 if not pause: return
 Path(pause).write_text(json.dumps({'pid':os.getpid(),'event_uuid':str(row.event_uuid),'stage':'after_business_commit'}), encoding='utf-8')
 status('after_business_commit', event_uuid=str(row.event_uuid))
 release=os.environ.get('WORKER_AFTER_BUSINESS_COMMIT_RELEASE_FILE')
 if release:
  while not Path(release).exists(): time.sleep(.05)
def status(stage, **extra):
 import json
 if status_file:
  with open(status_file,'a',encoding='utf-8') as f:
   f.write(json.dumps({'pid':os.getpid(),'worker_id':worker_id,'stage':stage,**extra})+'\n')
def structured_code(response):
 try: data=response.json()
 except Exception: return None
 def walk(v):
  if isinstance(v,dict):
   if isinstance(v.get('message'),str) and len(v['message'])<100 and v['message'].replace('_','').isalnum() and v['message'].upper()==v['message']: return v['message']
   for k in ('error_code','code'):
    if isinstance(v.get(k),str) and len(v[k])<100 and v[k].replace('_','').isalnum() and v[k].upper()==v[k]: return v[k]
   for child in v.values():
    found=walk(child)
    if found: return found
  elif isinstance(v,list):
   for child in v:
    found=walk(child)
    if found: return found
  return None
 return walk(data)
status('runner_started')
from app.config import settings
peer=uuid.UUID(os.environ['WORKER_PEER']); channel=os.environ['WORKER_CHANNEL']; target=os.environ['WORKER_TARGET']; secret=os.environ['WORKER_SECRET']; fail=os.environ.get('WORKER_PAUSE')=='1'
carrier=uuid.UUID(os.environ.get('WORKER_CARRIER', str(peer)))
publisher_scope_device=uuid.UUID(os.environ['WORKER_PUBLISHER_DEVICE'])
publisher_scope_generation=uuid.UUID(os.environ['WORKER_PUBLISHER_GENERATION'])
publisher_scope_clinic=uuid.UUID(os.environ['WORKER_PUBLISHER_CLINIC'])
if os.environ.get('WORKER_LEASE_SECONDS'):
 transport_service.DELIVERY_LEASE_SECONDS=int(os.environ['WORKER_LEASE_SECONDS'])
def after_claim(events):
 status('after_claim_entered', count=len(events))
 import json
 log=os.environ.get('WORKER_CLAIM_LOG')
 if log:
  with open(log,'a',encoding='utf-8') as f:
   for e in events: f.write(json.dumps({'worker_id':worker_id,'event_uuid':e['event_uuid'],'lease_token':e['lease_token'],'claimed_at':time.time()})+'\\n')
 print('CLAIMED '+','.join(e['event_uuid'] for e in events),flush=True)
 status('coordination_signal_sent', count=len(events))
 release=os.environ.get('WORKER_RELEASE_FILE')
 if release:
  import pathlib
  while not pathlib.Path(release).exists(): time.sleep(.05)
def sender(events):
 if fail: raise RuntimeError('synthetic worker stop before network')
 h={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret}
 body={'contract_version':'2.1','source_clinic_uuid':events[0]['source_clinic_uuid'],'source_device_uuid':events[0]['source_device_uuid'],'source_generation_uuid':events[0]['source_generation_uuid'],'channel':channel,'publisher_device_uuid':events[0].get('publication_source_device_uuid') or events[0]['source_device_uuid'],'publisher_generation_uuid':events[0].get('publication_source_generation_uuid') or events[0]['source_generation_uuid'],'publisher_clinic_uuid':events[0]['source_clinic_uuid'],'events':events,'limit':len(events)}
 started=time.monotonic()
 try:
  r=requests.post(target+'/api/v1/sync/v2/receive',json=body,headers=h,timeout=20)
 except Exception as exc:
  print(f'worker stage=send exception={type(exc).__name__} elapsed_ms={int((time.monotonic()-started)*1000)}',file=sys.stderr,flush=True); raise
 try: safe_code=r.json().get('data',{}).get('code') or r.json().get('detail',{}).get('details',{}).get('code')
 except Exception: safe_code='invalid_response'
 if not safe_code: safe_code=structured_code(r)
 print(f'worker stage=parse_response http={r.status_code} code={safe_code} elapsed_ms={int((time.monotonic()-started)*1000)} batch={len(events)}',file=sys.stderr,flush=True)
 r.raise_for_status()
 data=r.json().get('data',{})
 if data.get('accepted',0)+data.get('duplicates',0) != len(events): raise RuntimeError('RECEIVE_RESULT_EVENT_COUNT_MISMATCH')
 status('receive_committed', count=len(events))
 receive_release=os.environ.get('WORKER_AFTER_RECEIVE_RELEASE_FILE')
 if receive_release:
  import pathlib
  status('before_ack_waiting', count=len(events))
  while not pathlib.Path(receive_release).exists(): time.sleep(.05)
 from app.services.sync_transport_service import SyncTransportService
 for e in events:
  ack_target=os.environ.get('WORKER_ACK_TARGET', os.environ['WORKER_SOURCE'])
  ar=requests.post(ack_target+'/api/v1/sync/v2/ack',json={'contract_version':'2.1','event_uuid':e['event_uuid'],'channel':channel,'lease_token':e['lease_token'],'publisher_device_uuid':e.get('publication_source_device_uuid') or e['source_device_uuid'],'publisher_generation_uuid':e.get('publication_source_generation_uuid') or e['source_generation_uuid'],'publisher_clinic_uuid':e['source_clinic_uuid']},headers=h,timeout=20)
  ack_code=structured_code(ar)
  print(f'worker stage=ack event={e["event_uuid"]} http={ar.status_code} code={ack_code or "none"}',file=sys.stderr,flush=True)
  if ar.status_code >= 400:
   if ack_code == 'SYNC_RELAY_NOT_AUTHORIZED': raise RuntimeError('RELAY_AUTHORIZATION_REVOKED')
   ar.raise_for_status()
def before_send(events):
 from app.services.sync_transport_service import SyncTransportService
 try:
  with factory() as db:
   from app.models.sync_transport import SyncRelayAuthorization
   from sqlalchemy import select
   origin=uuid.UUID(events[0]['source_device_uuid']); generation=uuid.UUID(events[0]['source_generation_uuid'])
   active = db.scalar(select(SyncRelayAuthorization.id).where(SyncRelayAuthorization.carrier_device_uuid==carrier, SyncRelayAuthorization.origin_device_uuid==origin, SyncRelayAuthorization.origin_generation_uuid==generation, SyncRelayAuthorization.destination_device_uuid==peer, SyncRelayAuthorization.channel==channel, SyncRelayAuthorization.is_active.is_(True))) is not None
   status('before_send_authorization_checked', active=active, database=settings.database_name, exact_total=db.scalar(select(func.count()).select_from(SyncRelayAuthorization).where(SyncRelayAuthorization.carrier_device_uuid==peer, SyncRelayAuthorization.destination_device_uuid==peer, SyncRelayAuthorization.channel==channel)))
   SyncTransportService().authorize_relay(db, carrier_device_uuid=carrier,
    origin_device_uuid=uuid.UUID(events[0]['source_device_uuid']),
    origin_generation_uuid=uuid.UUID(events[0]['source_generation_uuid']),
    destination_device_uuid=peer, channel=channel)
 except Exception as exc:
  detail=getattr(exc, 'detail', {})
  if isinstance(detail, dict) and detail.get('details', {}).get('error_code') == 'SYNC_RELAY_NOT_AUTHORIZED':
   raise RuntimeError("RELAY_AUTHORIZATION_REVOKED") from exc
  raise
def negotiate_proof_capability():
 from recovery_tests.proof_capability_negotiation import interpret_capability_response
 target_cap=os.environ.get('WORKER_CAPABILITY_TARGET')
 if not target_cap: return 'negotiation_failed'
 try:
  versions=json.loads(os.environ.get('WORKER_CAPABILITY_VERSIONS','[1]'))
  scope=os.environ.get('WORKER_CONNECTION_SCOPE',channel)
  origin_device = os.environ.get('WORKER_ORIGIN_DEVICE')
  origin_generation = os.environ.get('WORKER_ORIGIN_GENERATION')
  if not origin_device or not origin_generation:
   return 'negotiation_failed'
  r=requests.post(target_cap+'/api/v1/sync/v2/proof-capabilities',json={
   'peer_device_uuid':str(peer), 'connection_scope':scope,
   'origin_device_uuid':origin_device,
   'origin_generation_uuid':origin_generation,
   'supported_versions':versions}, headers={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret},timeout=10)
  headers={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret}
  decision=interpret_capability_response(r, target=target_cap, peer=peer, scope=scope, origin_device=origin_device, origin_generation=origin_generation, versions=versions, headers=headers)
  if decision == 'negotiation_failed': return decision
  sequence = r.json().get('data', {}).get('advertisement_sequence')
  key=(str(peer),scope,origin_device,origin_generation)
  with _capability_lock:
   previous=_latest_capability_sequence.get(key,0)
   if sequence < previous: return 'negotiation_failed'
   _latest_capability_sequence[key]=sequence
  return decision
 except Exception:
  return 'negotiation_failed'
proof_claims={}
def pending_proof_loader():
 from app.services.sync_transport_service import SyncTransportService
 with factory() as db:
  rows=SyncTransportService().claim_proof_batch(db,peer_device_uuid=peer,channel=channel,limit=20)
  out=[]
  for delivery,proof in rows:
   proof_claims[str(proof.proof_uuid)]={'delivery_id':delivery.id,'lease_token':str(delivery.lease_token)}
   out.append({'proof_uuid':str(proof.proof_uuid),'event_uuid':str(proof.event_uuid),'content_sha256':proof.content_sha256,'proof':proof.proof,'source_device_uuid':os.environ['WORKER_ORIGIN_DEVICE'],'source_generation_uuid':os.environ['WORKER_ORIGIN_GENERATION'],'source_clinic_uuid':proof.proof.get('clinic_uuid'),'channel':channel})
  pause=os.environ.get('PROOF_AFTER_CLAIM_PAUSE_FILE'); release=os.environ.get('PROOF_AFTER_CLAIM_RELEASE_FILE')
  if out and pause and release:
   Path(pause).write_text(json.dumps({'pid':os.getpid(),'count':len(out)}),encoding='utf-8')
   deadline=time.monotonic()+float(os.environ.get('PROOF_CLAIM_HOOK_TIMEOUT','20'))
   while not Path(release).exists() and time.monotonic()<deadline: time.sleep(.05)
   if not Path(release).exists(): raise RuntimeError('PROOF_CLAIM_HOOK_TIMEOUT')
  return out
def proof_sender(proofs):
 h={'X-Sync-Device-UUID':str(peer),'X-Sync-Device-Secret':secret}
 for item in proofs:
  local=proof_claims[item['proof_uuid']]
  r=requests.post(target+'/api/v1/sync/v2/proof-receive',json={'contract_version':'2.1',**item},headers=h,timeout=20); r.raise_for_status(); data=r.json().get('data',{})
  if os.environ.get('PROOF_TEST_MUTATE_RECEIPT')=='1': data=dict(data); data['event_uuid']=str(uuid.uuid4())
  import hashlib
  from app.services.proof_verification_service import canonical_bytes
  expected_hash=hashlib.sha256(canonical_bytes(item['proof'])).hexdigest()
  receipt_fields={'proof_uuid':item['proof_uuid'],'event_uuid':item['event_uuid'],'content_sha256':item['content_sha256'],'source_device_uuid':item['source_device_uuid'],'source_generation_uuid':item['source_generation_uuid'],'channel':channel,'proof_sha256':expected_hash}
  if any(data.get(key)!=value for key,value in receipt_fields.items()):
   raise RuntimeError('PROOF_RECEIPT_BINDING_MISMATCH')
  print(f"worker stage=proof_receive http={r.status_code} proof={item['proof_uuid']}",flush=True)
  pause=os.environ.get('PROOF_AFTER_RECEIVE_PAUSE_FILE'); release=os.environ.get('PROOF_AFTER_RECEIVE_RELEASE_FILE')
  if pause and release:
   Path(pause).write_text(json.dumps({'pid':os.getpid(),'proof_uuid':item['proof_uuid']}),encoding='utf-8')
   while not Path(release).exists(): time.sleep(.05)
  ack_url=(target+'/api/v1/sync/v2/proof-ack')
  if os.environ.get('PROOF_TEST_FAIL_ACK')=='1': ack_url=target+'/api/v1/sync/v2/proof-ack-test-failure'
  a=requests.post(ack_url,json={'contract_version':'2.1','proof_uuid':item['proof_uuid'],'receipt_uuid':data['receipt_uuid'],'source_device_uuid':item['source_device_uuid'],'source_generation_uuid':item['source_generation_uuid'],'channel':channel},headers=h,timeout=20); print(f"worker stage=proof_ack http={a.status_code} proof={item['proof_uuid']}",flush=True); a.raise_for_status()
  with factory() as db:
   from app.services.sync_transport_service import SyncTransportService
   SyncTransportService().acknowledge_proof_delivery(db,delivery_id=local['delivery_id'],peer_device_uuid=peer,channel=channel,lease_token=uuid.UUID(local['lease_token']))
engine=create_engine(settings.database_url); factory=sessionmaker(bind=engine)
if os.environ.get('WORKER_RELAY') == '1':
 from app.services.sync_transport_service import SyncTransportService
 relay=SyncTransportService()
 def _after_publish(event_uuid, publish_sequence):
  pause=os.environ.get('RELAY_AFTER_PUBLISH_PAUSE_FILE')
  if not pause: return
  import pathlib
  pathlib.Path(pause).write_text(json.dumps({'pid':os.getpid(),'stage':'after_publish','event_uuid':str(event_uuid),'publish_sequence':publish_sequence}), encoding='utf-8')
  status('relay_after_publish_waiting', publish_sequence=publish_sequence)
  release=os.environ.get('RELAY_AFTER_PUBLISH_RELEASE_FILE')
  if release:
   while not pathlib.Path(release).exists(): time.sleep(.05)
 def _before_relay():
  pause=os.environ.get('RELAY_BEFORE_RELAY_PAUSE_FILE')
  if not pause: return
  import pathlib
  pathlib.Path(pause).write_text(json.dumps({'pid':os.getpid(),'stage':'before_relay'}), encoding='utf-8')
  status('relay_before_waiting')
  release=os.environ.get('RELAY_BEFORE_RELAY_RELEASE_FILE')
  if release:
   while not pathlib.Path(release).exists(): time.sleep(.05)
 _before_relay()
 with factory() as db:
  result=relay.relay_inbox_once(db, carrier_device_uuid=uuid.UUID(os.environ['RELAY_CARRIER']), publisher_device_uuid=uuid.UUID(os.environ['RELAY_PUBLISHER']), publisher_generation_uuid=uuid.UUID(os.environ['RELAY_GENERATION']), destination_device_uuid=uuid.UUID(os.environ['RELAY_DESTINATION']), channel=channel, limit=int(os.environ.get('RELAY_LIMIT','100')), _after_publish=_after_publish)
  status('relay_completed', published=result.get('published',0))
 raise SystemExit(0)
worker=SyncTransportWorker(factory,peer_device_uuid=peer,channel=channel,
                           publisher_device_uuid=publisher_scope_device,
                           publisher_generation_uuid=publisher_scope_generation,
                           publisher_clinic_uuid=publisher_scope_clinic,
                           after_application_business_commit=after_application_business_commit if os.environ.get('WORKER_AFTER_BUSINESS_COMMIT_FILE') else None,
                           sender=sender,batch_size=int(os.environ.get('WORKER_BATCH_SIZE','2')),after_claim=after_claim if os.environ.get('WORKER_COORDINATE')=='1' else None,before_send=before_send,proof_capability_negotiator=negotiate_proof_capability if os.environ.get('WORKER_CAPABILITY_TARGET') else None,proof_sender=proof_sender if os.environ.get('PROOF_TRANSPORT_ENABLED')=='1' else None,pending_proof_loader=pending_proof_loader if os.environ.get('PROOF_TRANSPORT_ENABLED')=='1' else None)
status('worker_initialized')
if os.environ.get('WORKER_APPLY_INBOX') == '1':
    worker.application_enabled = True
    status('inbox_application_started')
    applied = worker.run_application_once(limit=int(os.environ.get('WORKER_APPLY_INBOX_LIMIT', '10')))
    status('inbox_application_completed', applied=applied)
original_claim=worker.service.claim_batch
def traced_claim(*args, **kwargs):
 status('before_claim')
 result=original_claim(*args, **kwargs)
 status('claim_returned', count=len(result))
 return result
worker.service.claim_batch=traced_claim
for _ in range(int(os.environ.get('WORKER_CYCLES','4'))):
    if worker.application_enabled:
        worker.run_application_once(limit=int(os.environ.get('WORKER_APPLY_INBOX_LIMIT', '10')))
    if worker.run_once() == 0:
        break
