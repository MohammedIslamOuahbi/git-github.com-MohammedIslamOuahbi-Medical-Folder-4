"""Pure application gate for 5A; it never writes business tables or opens guards."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class EligibilityDecision:
    decision: str
    reason_code: str

def evaluate_application_eligibility(*, event: Any, verification: Any | None,
                                     expected_clinic_uuid: Any,
                                     expected_origin_service_uuid: Any,
                                     expected_origin_device_uuid: Any,
                                     expected_entity_uuid: Any,
                                     expected_content_sha256: str) -> EligibilityDecision:
    """Evaluate current evidence only. ``eligible`` is intentionally unreachable
    unless the persisted verifier has produced every required valid result.
    """
    if verification is None:
        return EligibilityDecision("blocked", "PROOF_VERIFICATION_MISSING")
    if str(getattr(verification, "event_uuid", "")) != str(getattr(event, "event_uuid", "")):
        return EligibilityDecision("blocked", "PROOF_EVENT_MISMATCH")
    if str(getattr(verification, "content_sha256", "")) != str(expected_content_sha256):
        return EligibilityDecision("blocked", "PROOF_CONTENT_MISMATCH")
    refs = getattr(verification, "evidence_refs", {}) or {}
    if refs.get("clinic_uuid") != str(expected_clinic_uuid):
        return EligibilityDecision("blocked", "PROOF_CLINIC_SCOPE_MISMATCH")
    if refs.get("origin_service_uuid") != str(expected_origin_service_uuid):
        return EligibilityDecision("blocked", "PROOF_SERVICE_SCOPE_MISMATCH")
    if refs.get("origin_device_uuid") != str(expected_origin_device_uuid):
        return EligibilityDecision("blocked", "PROOF_DEVICE_SCOPE_MISMATCH")
    checks = {
        "signature_result": "valid",
        "binding_result": "valid",
        "key_trust_result": "active",
        "delegation_result": "valid",
        "time_result": "time_valid",
    }
    for field, expected in checks.items():
        if getattr(verification, field, None) != expected:
            return EligibilityDecision("blocked", f"PROOF_{field.upper()}_NOT_VALID")
    if str(getattr(event, "entity_uuid", "")) != str(expected_entity_uuid):
        return EligibilityDecision("blocked", "PROOF_ENTITY_MISMATCH")
    return EligibilityDecision("eligible", "ALL_CURRENT_EVIDENCE_VALID")
