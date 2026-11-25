"""Real Ed25519 issue/verify rejection matrix; no DB or business writes."""
import base64, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.services.proof_issuer_service import MemoryKeyProvider
from app.services.authorization_evidence_service import issue_authorization_evidence, verify_authorization_evidence, evidence_fingerprint

def main():
    private=Ed25519PrivateKey.generate(); key_id="auth-test-key"; provider=MemoryKeyProvider({key_id: private})
    issuer=uuid.uuid4(); user=uuid.uuid4(); op=uuid.uuid4(); event=uuid.uuid4(); entity=uuid.uuid4(); clinic=uuid.uuid4(); scope=f"clinic:{clinic}:workers:create"
    ev=issue_authorization_evidence(key_provider=provider,key_id=key_id,issuer_uuid=issuer,issuer_scope=scope,user_uuid=user,operation_uuid=op,event_uuid=event,entity_type="workers",entity_uuid=entity,content_sha256="a"*64,clinic_uuid=clinic,scope=scope,policy_version="5A-1")
    pub=base64.b64encode(private.public_key().public_bytes_raw()).decode(); expected={"subject_user_uuid":str(user),"operation_uuid":str(op),"event_uuid":str(event),"entity_type":"workers","entity_uuid":str(entity),"content_sha256":"a"*64,"clinic_uuid":str(clinic),"scope":scope,"policy_version":"5A-1"}
    def check(name, candidate, exp, issuer_uuid=issuer, issuer_scope=scope):
        got=verify_authorization_evidence(candidate,public_key_b64=pub,expected=exp,trusted_issuer_uuid=issuer_uuid,trusted_issuer_scope=issuer_scope); assert got[0]=="accepted_test_only" if name=="authorized" else got[0]=="rejected"; print(name,got)
    check("authorized",ev,expected)
    check("user_mismatch",ev|{"subject_user_uuid":str(uuid.uuid4())},expected)
    check("operation_mismatch",ev|{"operation_uuid":str(uuid.uuid4())},expected)
    check("entity_mismatch",ev|{"entity_uuid":str(uuid.uuid4())},expected)
    check("content_mismatch",ev|{"content_sha256":"b"*64},expected)
    check("scope_mismatch",ev,expected,issuer_scope="other-scope")
    check("issuer_mismatch",ev,expected,issuer_uuid=uuid.uuid4())
    tampered=dict(ev); tampered["signature"]="A"*len(ev["signature"]); check("signature_tampered",tampered,expected)
    check("unknown_policy",ev,dict(expected,policy_version="unknown"))
    print("fingerprint=",evidence_fingerprint(ev),"business_application=0 eligible_production=0 applied=0")
if __name__ == "__main__": main()
