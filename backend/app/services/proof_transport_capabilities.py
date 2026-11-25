from __future__ import annotations
PROOF_TRANSPORT_VERSION=1
def negotiate_proof_transport(*,authenticated_peer_uuid,connection_scope,peer_uuid,advertised_versions,local_versions=(1,)):
 if authenticated_peer_uuid!=peer_uuid: return {'status':'rejected','reason':'PEER_IDENTITY_MISMATCH'}
 if not connection_scope: return {'status':'rejected','reason':'CONNECTION_SCOPE_REQUIRED'}
 supported=sorted(set(advertised_versions).intersection(local_versions))
 if not supported: return {'status':'unsupported','reason':'PROOF_TRANSPORT_UNSUPPORTED'}
 return {'status':'accepted','proof_transport_version':supported[-1],'peer_uuid':str(peer_uuid),'scope':connection_scope}

def worker_proof_transport_decision(negotiation_result):
 if negotiation_result.get('status')=='accepted' and negotiation_result.get('proof_transport_version')==1: return 'supported'
 if negotiation_result.get('status')=='unsupported': return 'unsupported'
 return 'negotiation_failed'
