"""Isolated proof issuer. Production key custody is deliberately not provided."""
from __future__ import annotations
import base64, uuid
from datetime import datetime, timezone
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.origin_proof import OriginProof
from app.models.proof_pending import OriginProofRequest
from app.models.proof_trust import ProofTrustedKey, ProofDelegation
from app.models.sync_change import SyncChange
from app.services.proof_verification_service import canonical_bytes, verify_key_scope, verify_delegation_scope

class KeyProvider(Protocol):
    def private_key(self, key_id: str): ...

class MemoryKeyProvider:
    """Test-only provider; keys live only in this Python process."""
    def __init__(self, keys: dict[str, object]): self._keys = dict(keys)
    def private_key(self, key_id: str):
        key = self._keys.get(key_id)
        if key is None: raise ValueError("SIGNING_KEY_UNAVAILABLE")
        return key

class ProofIssuerService:
    def __init__(self, key_provider: KeyProvider, *, key_id: str): self.keys = key_provider; self.key_id = key_id

    def issue(self, db: Session, *, request_uuid: uuid.UUID) -> dict:
        request = db.scalar(select(OriginProofRequest).where(OriginProofRequest.request_uuid == request_uuid).with_for_update())
        if request is None: raise ValueError("PROOF_REQUEST_NOT_FOUND")
        change = db.scalar(select(SyncChange).where(SyncChange.change_uuid == request.event_uuid))
        if change is None: raise ValueError("SOURCE_EVENT_NOT_FOUND")
        if change.content_sha256 != request.content_sha256 or change.operation_uuid != request.operation_uuid:
            raise ValueError("PROOF_REQUEST_EVENT_MISMATCH")
        existing = db.scalar(select(OriginProof).where(OriginProof.request_uuid == request_uuid))
        if existing is not None: return existing.proof
        key_id = self.key_id
        if not key_id: raise ValueError("SIGNING_KEY_ID_REQUIRED")
        key = db.get(ProofTrustedKey, key_id)
        if key is None: raise ValueError("TRUSTED_KEY_NOT_FOUND")
        proof = {
            "event_uuid": str(change.change_uuid), "content_sha256": change.content_sha256,
            "clinic_uuid": str(request.clinic_uuid), "entity_type": change.entity_type,
            "entity_uuid": str(change.entity_uuid), "operation": change.operation,
            "revision_uuid": str(change.revision_uuid), "parent_revision_uuid": str(change.parent_revision_uuid) if getattr(change, "parent_revision_uuid", None) else None,
            "origin_user_uuid": str(change.source_user_uuid), "origin_device_uuid": str(change.source_device_uuid),
            "origin_service_uuid": str(key.origin_service_uuid),
            "operation_uuid": str(change.operation_uuid), "authorization_policy_version": request.policy_version,
            "authorization_reference": request.last_reason_code, "proof_format_version": "1",
            "signing_key_id": key_id, "issued_at": datetime.now(timezone.utc).isoformat(),
        }
        delegation = db.scalar(select(ProofDelegation).where(ProofDelegation.delegation_uuid == uuid.UUID(request.last_reason_code)))
        if verify_key_scope(proof, key, clinic_uuid=request.clinic_uuid, origin_service_uuid=key.origin_service_uuid, origin_device_uuid=request.origin_device_uuid) != "valid":
            raise ValueError("KEY_SCOPE_INVALID")
        if verify_delegation_scope(proof, delegation, clinic_uuid=request.clinic_uuid, origin_service_uuid=key.origin_service_uuid, user_uuid=change.source_user_uuid, entity_type=change.entity_type, operation=change.operation, policy_version=request.policy_version) != "valid":
            raise ValueError("DELEGATION_SCOPE_INVALID")
        private = self.keys.private_key(key_id)
        proof["signature"] = base64.b64encode(private.sign(canonical_bytes(proof))).decode("ascii")
        db.add(OriginProof(proof_uuid=uuid.uuid4(), request_uuid=request_uuid, event_uuid=change.change_uuid, content_sha256=change.content_sha256, signing_key_id=key_id, proof=proof, created_at=datetime.now(timezone.utc)))
        request.status = "proof_issued_test_only"; request.updated_at = datetime.now(timezone.utc)
        db.flush()
        if db.info.get("proof_issuer_fail_after_insert"):
            raise RuntimeError("INJECTED_PROOF_ISSUER_FAILURE_AFTER_INSERT")
        return proof
