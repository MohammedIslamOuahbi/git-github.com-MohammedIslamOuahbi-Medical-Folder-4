import base64, os, uuid, time
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.services.revocation_chain_service import *
from app.services.revocation_checkpoint_service import *
from app.services.time_freshness_service import TestTimeAuthority, begin_challenge, evaluate_freshness
from app.models.revocation_checkpoint import RevocationCheckpoint
DB=os.environ["DATABASE_URL"]; engine=create_engine(DB)
def chain_record(k,a,scope,n,prev):
 x={"record_uuid":uuid.uuid4(),"authority_uuid":str(a),"chain_scope":scope,"contract_version":"revocation-chain-v1","canonicalization_version":CHAIN_CANONICALIZATION,"sequence":n,"previous_record_hash":prev,"record":{"target_type":"key","target_ref":str(uuid.uuid4()),"reason":"test"}}
 x["record_hash"]=record_hash(x); x["signature"]=base64.b64encode(k.sign(record_bytes(x))).decode(); return x
def checkpoint(k,a,scope,seq,head,ch,dest):
 x={"checkpoint_uuid":str(uuid.uuid4()),"authority_uuid":str(a),"authority_key_id":"test-revocation-authority","chain_scope":scope,"contract_version":"revocation-checkpoint-v1","policy_version":"test-policy-v1","covered_sequence":seq,"covered_chain_hash":head,"challenge":ch,"destination_device_uuid":str(dest)}
 x["signature"]=base64.b64encode(k.sign(canonical_checkpoint_bytes(x))).decode(); return x
def put_chain(x,pub):
 with Session(engine) as s: r=store_chain_record(s,x,authority_public_key=pub); s.commit(); return r
def main():
 k=Ed25519PrivateKey.generate(); pub=base64.b64encode(k.public_key().public_bytes_raw()).decode(); a=uuid.uuid4(); scope='checkpoint:'+str(uuid.uuid4()); dest=uuid.uuid4(); r1=chain_record(k,a,scope,1,GENESIS_RECORD_HASH); r2=chain_record(k,a,scope,2,r1['record_hash']); put_chain(r1,pub); put_chain(r2,pub)
 auth=TestTimeAuthority(); req=begin_challenge(proof_uuid=uuid.uuid4(),event_uuid=uuid.uuid4(),authority_scope=scope); req.update(destination_uuid=str(dest),policy_version='test-policy-v1'); resp=auth.sign(req); policy={'authority_id':'test-time-authority','test_only':True,'max_rtt_seconds':5,'valid_from':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),'valid_until':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()}; fresh=evaluate_freshness(resp,req,auth,ended_monotonic=req['started_monotonic']+1,policy=policy)
 cp=checkpoint(k,a,scope,2,r2['record_hash'],req['challenge'],dest)
 with Session(engine) as s:
  assert verify_checkpoint_signature(cp,pub)=='valid'; store_checkpoint(s,cp,public_key=pub); s.commit(); cov=check_coverage(s,authority_uuid=a,chain_scope=scope,checkpoint_sequence=2,checkpoint_hash=r2['record_hash'])
 assert cov['status']=='complete' and fresh['accepted_test_only']; print('healthy_current_complete',{'freshness':fresh['time_result'],'coverage':cov['status'],'accepted_test_only':True})
 late=evaluate_freshness(auth.sign(begin_challenge(proof_uuid=req['proof_uuid'],event_uuid=req['event_uuid'],authority_scope=scope)|{'destination_uuid':str(dest),'policy_version':'test-policy-v1'}),req,auth,ended_monotonic=req['started_monotonic']+6,policy=policy); assert late['accepted_test_only'] is False; print('late_rejected',late['freshness'])
 bad=dict(resp); bad['challenge']='wrong'; assert evaluate_freshness(bad,req,auth,ended_monotonic=req['started_monotonic']+1,policy=policy)['accepted_test_only'] is False; print('challenge_mismatch_rejected=1')
 bad_dest=dict(resp); bad_dest['destination_uuid']=str(uuid.uuid4()); assert evaluate_freshness(bad_dest,req,auth,ended_monotonic=req['started_monotonic']+1,policy=policy)['accepted_test_only'] is False; print('destination_mismatch_rejected=1')
 bad_policy=dict(resp); bad_policy['policy_version']='other'; assert evaluate_freshness(bad_policy,req,auth,ended_monotonic=req['started_monotonic']+1,policy=policy)['accepted_test_only'] is False; print('policy_mismatch_rejected=1')
 with Session(engine) as s: inc=check_coverage(s,authority_uuid=a,chain_scope='missing:'+str(uuid.uuid4()),checkpoint_sequence=2,checkpoint_hash=r2['record_hash']); assert inc['status']=='incomplete'; print('recent_but_incomplete',inc)
 replay=evaluate_freshness(resp,req,auth,ended_monotonic=req['started_monotonic']+1,policy=policy); assert replay['accepted_test_only'] is False; print('replay_rejected=1')
 print('business_application=0')
if __name__=='__main__': main()
