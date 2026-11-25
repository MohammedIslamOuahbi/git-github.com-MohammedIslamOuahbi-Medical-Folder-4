"""P2-A verification primitives; never issues proofs or applies business data."""
from __future__ import annotations
import base64, json, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

CANONICALIZATION_VERSION="jcs-rfc8785-compatible-v1"; PROOF_FORMAT_VERSION="1"
def canonical_bytes(proof: dict) -> bytes:
    allowed={k:proof[k] for k in ("event_uuid","content_sha256","clinic_uuid","entity_type","entity_uuid","operation","revision_uuid","parent_revision_uuid","origin_user_uuid","origin_device_uuid","operation_uuid","authorization_policy_version","authorization_reference","proof_format_version","signing_key_id","issued_at") if k in proof}
    return json.dumps(allowed,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def verify_signature(proof: dict, public_key_b64: str) -> str:
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(proof["signature"]),canonical_bytes(proof)); return "valid"
    except (ValueError, KeyError, InvalidSignature): return "invalid"
def verify_binding(proof: dict, *, event_uuid, content_sha256, clinic_uuid, entity_type, entity_uuid, operation, revision_uuid) -> str:
    return "valid" if all(str(proof.get(k))==str(v) for k,v in {"event_uuid":event_uuid,"content_sha256":content_sha256,"clinic_uuid":clinic_uuid,"entity_type":entity_type,"entity_uuid":entity_uuid,"operation":operation,"revision_uuid":revision_uuid}.items()) else "mismatch"
