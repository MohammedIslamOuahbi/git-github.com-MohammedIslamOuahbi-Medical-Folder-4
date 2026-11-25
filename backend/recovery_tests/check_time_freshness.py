import uuid,math
from datetime import datetime,timezone,timedelta
from app.services.time_freshness_service import TestTimeAuthority,begin_challenge,evaluate_freshness

def signed(a,req,**changes):
 x={k:v for k,v in req.items() if k!='started_monotonic'}; x.update(changes); x.setdefault('destination_uuid',req['destination_uuid']); x.setdefault('policy_version',req['policy_version']); x.setdefault('authority_uncertainty_seconds',0); return a.sign(x)
def main():
 a=TestTimeAuthority(); p,e=uuid.uuid4(),uuid.uuid4(); req=begin_challenge(proof_uuid=p,event_uuid=e,authority_scope='test-scope'); req.update(destination_uuid=str(uuid.uuid4()),policy_version='test-policy'); res=signed(a,req); issued=datetime.fromisoformat(res['authority_issued_at']); base={'max_rtt_seconds':5,'authority_id':'test-time-authority','test_only':True}
 def run(name,policy,response=res,end=None,expect=False):
  a.used.clear(); r=evaluate_freshness(response,req,a,ended_monotonic=end if end is not None else req['started_monotonic'],policy=policy); assert r['accepted_test_only'] is expect; print(name,'=',r['time_result'],'accepted=',r['accepted_test_only'])
 run('valid_full_window',{**base,'valid_from':(issued-timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=10)).isoformat()},end=req['started_monotonic']+.1,expect=True)
 run('lower_before_valid_from',{**base,'valid_from':(issued+timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=20)).isoformat()},expect=False)
 run('upper_after_valid_until',{**base,'valid_from':(issued-timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=.01)).isoformat()},end=req['started_monotonic']+.1,expect=False)
 run('equal_boundaries',{**base,'valid_from':issued.isoformat(),'valid_until':issued.isoformat()},expect=True)
 run('expired_key',{**base,'valid_from':(issued-timedelta(seconds=2)).isoformat(),'valid_until':(issued-timedelta(seconds=1)).isoformat()},expect=False)
 run('expired_delegation',{**base,'valid_from':(issued+timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=2)).isoformat()},expect=False)
 run('wrong_destination',{**base,'valid_from':(issued-timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=10)).isoformat()},response=signed(a,req,destination_uuid=str(uuid.uuid4())),expect=False)
 run('wrong_policy',{**base,'valid_from':(issued-timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=10)).isoformat()},response=signed(a,req,policy_version='other'),expect=False)
 for label,val in [('negative',-1),('nan',float('nan')),('infinity',float('inf'))]:
  run('uncertainty_'+label,{**base,'valid_from':(issued-timedelta(seconds=1)).isoformat(),'valid_until':(issued+timedelta(seconds=10)).isoformat()},response=signed(a,req,authority_uncertainty_seconds=val),expect=False)
 print('clock_change_monotonic_stable=1')
if __name__=='__main__': main()

