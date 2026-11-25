"""Pure contract rejection matrix; never writes business data or eligible state."""
from types import SimpleNamespace
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.sync_application_evaluation_service import classify_authorization_evidence

EVENT = SimpleNamespace(event_uuid="event-1", entity_type="workers",
                        entity_uuid="entity-1", content_sha256="a" * 64)
BASE = {"evidence_uuid":"ev-1", "subject_user_uuid":"user-1",
        "operation_uuid":"op-1", "event_uuid":"event-1",
        "entity_type":"workers", "entity_uuid":"entity-1",
        "content_sha256":"a" * 64, "clinic_uuid":"clinic-1",
        "scope":"clinic:clinic-1", "policy_version":"5A-1",
        "issuer_uuid":"issuer-1", "signature":"signature"}

def check(name, value, expected):
    status, reason = classify_authorization_evidence(value, EVENT)
    assert (status, reason) == expected, (name, status, reason)
    print(name, status, reason)

def main():
    check("missing", None, ("missing", "AUTHORIZATION_EVIDENCE_MISSING"))
    check("invalid_signature_shape", {**BASE, "signature": None}, ("untrusted", "AUTHORIZATION_EVIDENCE_ISSUER_UNVERIFIED"))
    check("user_mismatch", {**BASE, "subject_user_uuid":"other"}, ("untrusted", "AUTHORIZATION_EVIDENCE_ISSUER_UNVERIFIED"))
    check("operation_mismatch", {**BASE, "operation_uuid":"other"}, ("untrusted", "AUTHORIZATION_EVIDENCE_ISSUER_UNVERIFIED"))
    check("content_mismatch", {**BASE, "content_sha256":"b" * 64}, ("mismatch", "AUTHORIZATION_EVIDENCE_CONTENT_SHA256_MISMATCH"))
    check("unknown_policy", {**BASE, "policy_version":"unknown"}, ("mismatch", "AUTHORIZATION_EVIDENCE_POLICY_VERSION_MISMATCH"))
    check("scope_present_but_untrusted", BASE, ("untrusted", "AUTHORIZATION_EVIDENCE_ISSUER_UNVERIFIED"))
    print("business_application=0 eligible_production=0 applied=0")

if __name__ == "__main__":
    main()
