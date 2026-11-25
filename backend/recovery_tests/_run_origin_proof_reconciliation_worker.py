import os,sys,json
from pathlib import Path
from sqlalchemy import create_engine,select
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models.origin_proof_transport import OriginProofTransportReceipt
from app.services.origin_proof_reconciliation_queue import consume_one
import requests,time,json
from app.services.time_freshness_service import begin_challenge,evaluate_freshness
class RemoteAuthority:
 def __init__(self,pub): self.public_key=pub; self.used=set()
event=os.environ.get("RECONCILIATION_EVENT_UUID"); proof=os.environ.get("RECONCILIATION_PROOF_UUID"); peer=os.environ.get("RECONCILIATION_PEER_UUID")
if not all((event,proof,peer)): raise RuntimeError("PROOF_RECONCILIATION_IDENTIFIERS_MISSING")
with SessionLocal() as db:
 row=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==event,OriginProofTransportReceipt.proof_uuid==proof,OriginProofTransportReceipt.peer_device_uuid==peer))
 if row is None: raise RuntimeError("PROOF_RECEIPT_NOT_FOUND:worker_database_is_not_target_or_receive_not_committed")
 print(json.dumps({"stage":"receipt_verified","proof_uuid":proof,"event_uuid":event,"receipt_uuid":str(row.receipt_uuid)},separators=(",",":")))
 fresh=None
 if os.environ.get("TIME_AUTHORITY_URL"):
  from app.models.origin_proof_transport import OriginProofTransportReceipt
  rec=db.scalar(__import__("sqlalchemy").select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.event_uuid==event,OriginProofTransportReceipt.proof_uuid==proof,OriginProofTransportReceipt.peer_device_uuid==peer))
  req=begin_challenge(proof_uuid=rec.proof_uuid,event_uuid=rec.event_uuid,authority_scope=os.environ["RECONCILIATION_CHAIN_SCOPE"]); req.update(destination_uuid=peer,policy_version=os.environ["RECONCILIATION_POLICY_VERSION"],checkpoint_uuid=os.environ.get("CHECKPOINT_UUID"),covered_sequence=int(os.environ.get("CHECKPOINT_COVERED_SEQUENCE","0")),covered_chain_hash=os.environ.get("CHECKPOINT_COVERED_CHAIN_HASH")); started=req["started_monotonic"]; resp=requests.post(os.environ["TIME_AUTHORITY_URL"],json={k:v for k,v in req.items() if k != "started_monotonic"},timeout=5).json(); ended=time.monotonic(); pol={"authority_id":"test-time-authority","test_only":True,"max_rtt_seconds":5,"valid_from":os.environ["TIME_VALID_FROM"],"valid_until":os.environ["TIME_VALID_UNTIL"]}; ev=evaluate_freshness(resp,req,RemoteAuthority(os.environ["TEST_TIME_AUTHORITY_PUBLIC_KEY"]),ended_monotonic=ended,policy=pol); print(json.dumps({"stage":"freshness_evaluation","result":ev},default=str),flush=True); fresh={"accepted_test_only":ev["accepted_test_only"],"time_result":ev["time_result"],"evidence_fingerprint":str(hash(json.dumps(resp,sort_keys=True))),"challenge":req["challenge"],"destination_device_uuid":peer,"policy_version":req["policy_version"],"checkpoint_uuid":req["checkpoint_uuid"],"covered_sequence":req["covered_sequence"],"covered_chain_hash":req["covered_chain_hash"] }
 r=consume_one(db,worker_id=os.environ.get("RECONCILIATION_WORKER_ID","reconcile-worker"),task_uuid=os.environ.get("RECONCILIATION_TASK_UUID"),authority_public_key=os.environ["TEST_REVOCATION_AUTHORITY_PUBLIC_KEY"],freshness_context=fresh); db.commit(); print(json.dumps(r,default=str))

