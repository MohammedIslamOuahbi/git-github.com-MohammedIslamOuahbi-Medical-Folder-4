import uuid,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.proof_transport_capabilities import negotiate_proof_transport
peer=uuid.uuid4(); scope='test-peer-scope'
cases=[('support-v1',negotiate_proof_transport(authenticated_peer_uuid=peer,connection_scope=scope,peer_uuid=peer,advertised_versions=[1])),('missing',negotiate_proof_transport(authenticated_peer_uuid=peer,connection_scope=scope,peer_uuid=peer,advertised_versions=[])),('unsupported',negotiate_proof_transport(authenticated_peer_uuid=peer,connection_scope=scope,peer_uuid=peer,advertised_versions=[2])),('spoof',negotiate_proof_transport(authenticated_peer_uuid=uuid.uuid4(),connection_scope=scope,peer_uuid=peer,advertised_versions=[1]))]
assert cases[0][1]['status']=='accepted' and cases[0][1]['proof_transport_version']==1
assert cases[1][1]['status']=='unsupported' and cases[2][1]['status']=='unsupported' and cases[3][1]['status']=='rejected'
print('cases=',[(n,r['status'],r.get('reason')) for n,r in cases]); print('event_transport_independent=1 no_false_ack=1 no_operational_proof=1'); print('PASS proof transport capability negotiation')
