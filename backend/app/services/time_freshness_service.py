import uuid,time,base64,math
from datetime import datetime,timezone,timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from .time_evidence_service import canonical_evidence_bytes

class TestTimeAuthority:
    def __init__(self):
        self.private=Ed25519PrivateKey.generate(); self.used=set()
    @property
    def public_key(self): return base64.b64encode(self.private.public_key().public_bytes_raw()).decode()
    def sign(self, request):
        payload={**request,'authority_issued_at':datetime.now(timezone.utc).isoformat(),'authority_key_id':'test-time-authority'}
        payload['signature']=base64.b64encode(self.private.sign(canonical_evidence_bytes(payload))).decode(); return payload

def begin_challenge(*,proof_uuid,event_uuid,authority_scope):
    return {'challenge':str(uuid.uuid4()),'proof_uuid':str(proof_uuid),'event_uuid':str(event_uuid),'authority_scope':authority_scope,'started_monotonic':time.monotonic()}

def verify_freshness(response, request, authority: TestTimeAuthority, *, ended_monotonic, max_round_trip_seconds=5):
    if response.get('challenge')!=request['challenge'] or response.get('proof_uuid')!=request['proof_uuid'] or response.get('event_uuid')!=request['event_uuid'] or response.get('authority_scope')!=request['authority_scope']: return 'rejected_binding'
    if response['challenge'] in authority.used: return 'rejected_replay'
    authority.used.add(response['challenge'])
    rtt=ended_monotonic-request['started_monotonic']
    if rtt>max_round_trip_seconds: return 'time_indeterminate'
    unsigned={k:v for k,v in response.items() if k!='signature'}
    try: Ed25519PublicKey.from_public_bytes(base64.b64decode(authority.public_key)).verify(base64.b64decode(response['signature']),canonical_evidence_bytes(unsigned))
    except (ValueError,KeyError,InvalidSignature): return 'rejected_signature'
    return 'time_indeterminate'  # legacy wrapper; use evaluate_freshness for explicit policy

def evaluate_freshness(response, request, authority: TestTimeAuthority, *, ended_monotonic, policy):
    """Return independent checks; acceptance is test-only and never application eligibility."""
    binding = all(response.get(k) == request.get(k) for k in ('challenge','proof_uuid','event_uuid','authority_scope','destination_uuid','policy_version','checkpoint_uuid','covered_sequence','covered_chain_hash'))
    rtt=ended_monotonic-request['started_monotonic']
    signature='invalid'
    try:
        unsigned={k:v for k,v in response.items() if k!='signature'}; Ed25519PublicKey.from_public_bytes(base64.b64decode(authority.public_key)).verify(base64.b64decode(response['signature']),canonical_evidence_bytes(unsigned)); signature='valid'
    except (ValueError,KeyError,InvalidSignature): pass
    authority_trusted=policy.get('authority_id')=='test-time-authority' and policy.get('test_only') is True
    issued=datetime.fromisoformat(response['authority_issued_at'].replace('Z','+00:00'))
    try: uncertainty=float(response.get('authority_uncertainty_seconds',0))
    except (TypeError,ValueError): uncertainty=float('nan')
    if not math.isfinite(uncertainty) or uncertainty < 0: return {'signature':signature,'binding': 'valid' if binding else 'mismatch','freshness':'invalid','authority':'test_only' if authority_trusted else 'untrusted','time_result':'time_indeterminate','accepted_test_only':False}
    freshness=math.isfinite(rtt) and rtt >= 0 and rtt <= policy['max_rtt_seconds']
    # Conservative asymmetric network model: authority time is measured before
    # transmission, so only RTT is added to the upper bound.
    lower=issued-timedelta(seconds=uncertainty); upper=issued+timedelta(seconds=uncertainty+rtt)
    valid_from=datetime.fromisoformat(policy['valid_from'].replace('Z','+00:00')); valid_until=datetime.fromisoformat(policy['valid_until'].replace('Z','+00:00'))
    window='valid' if lower >= valid_from and upper <= valid_until else 'indeterminate'
    accepted=all((signature=='valid',binding,freshness,authority_trusted,window=='valid'))
    if response.get('challenge') in authority.used: accepted=False
    if accepted: authority.used.add(response['challenge'])
    return {'signature':signature,'binding': 'valid' if binding else 'mismatch','freshness': 'valid' if freshness else 'timeout','authority': 'test_only' if authority_trusted else 'untrusted','time_interval':(lower.isoformat(),upper.isoformat()),'time_result':'time_valid_test_only' if accepted else 'time_indeterminate','accepted_test_only':accepted}
