"""Isolated authorization-evidence issuer/verifier.

This service is test-only until an operational issuer and historical
authorization store are approved.  It never writes application tables.
"""
from __future__ import annotations
import base64, hashlib, json, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from app.services.proof_issuer_service import KeyProvider

CANONICALIZATION_VERSION = "authorization-evidence-json-v1"
DOMAIN = "IBN-SINA/AUTHORIZATION-EVIDENCE/v1"
FIELDS = ("evidence_uuid", "issuer_key_id", "contract_version", "subject_user_uuid", "operation_uuid", "event_uuid",
          "entity_type", "entity_uuid", "content_sha256", "clinic_uuid",
          "scope", "policy_version", "issuer_uuid", "issuer_scope",
          "issued_at")

def canonical_authorization_bytes(evidence: dict) -> bytes:
    if any(k not in FIELDS and k != "signature" for k in evidence):
        raise ValueError("AUTHORIZATION_EVIDENCE_FIELD_UNSUPPORTED")
    body = {"domain": DOMAIN, "canonicalization_version": CANONICALIZATION_VERSION,
            **{k: evidence[k] for k in FIELDS}}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def issue_authorization_evidence(*, key_provider: KeyProvider, key_id: str,
                                 issuer_uuid: uuid.UUID, issuer_scope: str,
                                 user_uuid: uuid.UUID, operation_uuid: uuid.UUID,
                                 event_uuid: uuid.UUID, entity_type: str,
                                 entity_uuid: uuid.UUID, content_sha256: str,
                                 clinic_uuid: uuid.UUID, scope: str,
                                 policy_version: str, contract_version: str = "authorization-evidence-v1") -> dict:
    if not issuer_scope or issuer_scope != scope:
        raise ValueError("AUTHORIZATION_ISSUER_SCOPE_INVALID")
    if len(content_sha256) != 64:
        raise ValueError("AUTHORIZATION_CONTENT_HASH_INVALID")
    evidence = {"evidence_uuid": str(uuid.uuid4()), "issuer_key_id": key_id, "contract_version": contract_version, "subject_user_uuid": str(user_uuid),
        "operation_uuid": str(operation_uuid), "event_uuid": str(event_uuid),
        "entity_type": entity_type, "entity_uuid": str(entity_uuid),
        "content_sha256": content_sha256, "clinic_uuid": str(clinic_uuid),
        "scope": scope, "policy_version": policy_version,
        "issuer_uuid": str(issuer_uuid), "issuer_scope": issuer_scope,
        "issued_at": datetime.now(timezone.utc).isoformat()}
    private = key_provider.private_key(key_id)
    evidence["signature"] = base64.b64encode(private.sign(canonical_authorization_bytes(evidence))).decode()
    return evidence

def verify_authorization_evidence(evidence: dict, *, public_key_b64: str,
                                  expected: dict, trusted_issuer_uuid: uuid.UUID,
                                  trusted_issuer_scope: str) -> tuple[str, str]:
    try:
        if evidence.get("issuer_uuid") != str(trusted_issuer_uuid) or evidence.get("issuer_scope") != trusted_issuer_scope:
            return "rejected", "AUTHORIZATION_ISSUER_SCOPE_MISMATCH"
        for field, value in expected.items():
            if str(evidence.get(field)) != str(value):
                return "rejected", "AUTHORIZATION_" + field.upper() + "_MISMATCH"
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(
            base64.b64decode(evidence["signature"]), canonical_authorization_bytes(evidence))
    except (KeyError, ValueError, TypeError, InvalidSignature):
        return "rejected", "AUTHORIZATION_SIGNATURE_INVALID"
    return "accepted_test_only", "AUTHORIZATION_EVIDENCE_VALID_TEST_ONLY"

def evidence_fingerprint(evidence: dict) -> str:
    return hashlib.sha256(canonical_authorization_bytes(evidence)).hexdigest()

def store_local_evidence(db, evidence: dict):
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
    fp=evidence_fingerprint(evidence); existing=db.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.evidence_uuid==uuid.UUID(evidence["evidence_uuid"])))
    if existing:
        if existing.envelope_sha256 != fp or existing.envelope != evidence: raise ValueError("AUTHORIZATION_EVIDENCE_IDENTITY_CONFLICT")
        return existing
    row=AuthorizationEvidenceRecord(evidence_uuid=uuid.UUID(evidence["evidence_uuid"]),
        issuer_key_id=evidence.get("issuer_key_id"), contract_version=evidence.get("contract_version"),
        trust_reference=evidence.get("issuer_uuid"), event_uuid=uuid.UUID(evidence["event_uuid"]),
        operation_uuid=uuid.UUID(evidence["operation_uuid"]), content_sha256=evidence["content_sha256"],
        subject_user_uuid=uuid.UUID(evidence["subject_user_uuid"]), entity_type=evidence["entity_type"],
        entity_uuid=uuid.UUID(evidence["entity_uuid"]), clinic_uuid=uuid.UUID(evidence["clinic_uuid"]),
        scope=evidence["scope"], envelope=evidence, envelope_sha256=fp,
        created_at=datetime.now(timezone.utc)); db.add(row); db.flush(); return row

def issue_for_local_operation(db, *, key_provider: KeyProvider, key_id: str,
                              issuer_uuid: uuid.UUID, issuer_scope: str,
                              user, operation, event, clinic_uuid: uuid.UUID,
                              scope: str, policy_version: str,
                              permission_code: str) -> dict:
    """Issue only inside the local-write transaction after real permission check.

    `operation` is a LocalWriteOperation loaded from the trusted DB and
    `event` is its corresponding trusted SyncChange/transport event.  The
    permission service evaluates the current actor for this execution; the
    actor UUID and policy decision are then recorded in the operation's durable
    result payload.  Historical operations without that record stay blocked.
    """
    from app.services.permission_service import permission_service
    def clear_marker():
        db.info.pop("authorization_capture_operation_uuid", None)
    permission_service.require_permission(user, permission_code)
    if str(operation.actor_user_uuid) != str(user.uuid):
        raise ValueError("AUTHORIZATION_ACTOR_OPERATION_MISMATCH")
    existing = (operation.result_payload or {}).get("authorization_evidence")
    if existing is not None:
        if existing.get("content_sha256") != event.content_sha256:
            raise ValueError("AUTHORIZATION_OPERATION_CONTENT_CONFLICT")
        clear_marker(); return existing
    captured = db.info.get("authorization_capture_operation_uuid") == str(operation.operation_uuid)
    historical = (operation.result_payload or {}).get("authorization_decision") or {}
    if not captured and (historical.get("event_uuid") != str(event.change_uuid) or historical.get("content_sha256") != event.content_sha256):
        raise ValueError("AUTHORIZATION_HISTORICAL_DECISION_MISSING")
    evidence = issue_authorization_evidence(
        key_provider=key_provider, key_id=key_id, issuer_uuid=issuer_uuid,
        issuer_scope=issuer_scope, user_uuid=user.uuid,
        operation_uuid=operation.operation_uuid, event_uuid=event.change_uuid,
        entity_type=event.entity_type, entity_uuid=event.entity_uuid,
        content_sha256=event.content_sha256, clinic_uuid=clinic_uuid,
        scope=scope, policy_version=policy_version)
    # Keep the historical decision captured by the protected write intact;
    # the evidence is a separate reference produced from that decision.
    operation.result_payload = {**(operation.result_payload or {}),
        "authorization_evidence": evidence,
        "authorization_evidence_ref": {
            "evidence_uuid": evidence["evidence_uuid"],
            "envelope_sha256": evidence_fingerprint(evidence),
        }}
    db.flush()
    clear_marker()
    return evidence

def capture_authorization_execution(db, *, user, operation, event, permission_code: str,
                                    scope: str, policy_version: str) -> dict:
    """Capture the permission decision at execution time, after real auth.

    The marker is session-local and cannot be supplied through request payloads.
    It must be created by the protected local operation path in the same
    transaction before an issuer can read it.
    """
    from app.services.permission_service import permission_service
    permission_service.require_permission(user, permission_code)
    if str(operation.actor_user_uuid) != str(user.uuid):
        raise ValueError("AUTHORIZATION_ACTOR_OPERATION_MISMATCH")
    decision = {"user_uuid": str(user.uuid), "permission_code": permission_code,
                "scope": scope, "policy_version": policy_version,
                "event_uuid": str(event.change_uuid),
                "content_sha256": event.content_sha256}
    operation.result_payload = {**(operation.result_payload or {}),
        "authorization_decision": decision}
    db.info["authorization_capture_operation_uuid"] = str(operation.operation_uuid)
    db.flush()
    return decision
