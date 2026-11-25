"""Stage 5A evaluation only: records a durable decision and never applies business data."""
from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.models.sync_transport import SyncTransportEvent
from app.models.sync_application import SyncApplicationDecision, SyncApplicationAttempt
from app.models.local_revision import LocalRevision
from app.sync.registry import SYNC_ENTITY_REGISTRY
from app.models.company import Company
from app.models.branch import Branch
from app.models.drilling_site import DrillingSite

POLICY_VERSION = "5A-1"

def resolve_event_dependencies(db: Session, event) -> dict:
    """Resolve UUID relationships without applying the incoming entity."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    result = {}
    for name, model, key in (("company", Company, "company_uuid"), ("branch", Branch, "branch_uuid"), ("drilling_site", DrillingSite, "drilling_site_uuid")):
        raw = payload.get(key)
        row = None
        if raw:
            try: row = db.scalar(select(model).where(model.uuid == uuid.UUID(str(raw))))
            except (ValueError, TypeError): row = None
        result[name] = {"required_uuid": str(raw) if raw else None, "local_id": getattr(row, "id", None), "matched": row is not None}
    if result["branch"]["matched"] and result["company"]["matched"]:
        branch = db.get(Branch, result["branch"]["local_id"]); company = db.get(Company, result["company"]["local_id"])
        result["branch"]["belongs_to_company"] = branch.company_id == company.id
    if result["drilling_site"]["matched"] and result["branch"]["matched"]:
        site = db.get(DrillingSite, result["drilling_site"]["local_id"]); branch = db.get(Branch, result["branch"]["local_id"])
        result["drilling_site"]["belongs_to_branch"] = site.branch_id == branch.id
    return result

AUTHORIZATION_EVIDENCE_FIELDS = {
    "evidence_uuid", "subject_user_uuid", "operation_uuid", "event_uuid",
    "entity_type", "entity_uuid", "content_sha256", "clinic_uuid",
    "scope", "policy_version", "issuer_uuid", "signature",
}

def classify_authorization_evidence(evidence: dict | None, event, *, policy_version: str = POLICY_VERSION) -> tuple[str, str]:
    """Conservative contract gate; it never grants application authority.

    A future trusted issuer/verifier may replace the final untrusted result,
    but transport authentication, proof signing, or a role string cannot do
    so.  The function is deliberately pure so rejection cases are testable.
    """
    if not evidence:
        return "missing", "AUTHORIZATION_EVIDENCE_MISSING"
    missing = sorted(AUTHORIZATION_EVIDENCE_FIELDS - set(evidence))
    if missing:
        return "invalid", "AUTHORIZATION_EVIDENCE_FIELDS_MISSING:" + ",".join(missing)
    expected = {
        "event_uuid": str(event.event_uuid), "entity_type": event.entity_type,
        "entity_uuid": str(event.entity_uuid), "content_sha256": event.content_sha256,
        "operation_uuid": str(getattr(event, "operation_uuid", "")) if getattr(event, "operation_uuid", None) else None,
        "policy_version": policy_version,
    }
    for field, value in expected.items():
        if value is not None and str(evidence.get(field)) != value:
            return "mismatch", "AUTHORIZATION_EVIDENCE_" + field.upper() + "_MISMATCH"
    if evidence.get("verification_status") == "accepted_test_only":
        return "accepted_test_only", "AUTHORIZATION_EVIDENCE_VALID_TEST_ONLY"
    # No operational issuer/verifier exists yet.  Never treat this shape as
    # trusted merely because it contains a signature or a role-like value.
    return "untrusted", "AUTHORIZATION_EVIDENCE_ISSUER_UNVERIFIED"

def evaluate_event(db: Session, event_uuid: uuid.UUID, *, policy_version: str = POLICY_VERSION,
                   authorization_evidence: dict | None = None) -> SyncApplicationDecision:
    db.execute(select(text("pg_advisory_xact_lock(hashtext(:key))")).params(key=f"sync-evaluate:{event_uuid}"))
    event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == event_uuid))
    if event is None:
        raise ValueError("SYNC_EVENT_NOT_FOUND")
    # Fixture evidence is deliberately non-authoritative in 5A.  It is retained
    # only as bounded references; no caller can turn it into application trust.
    evidence = authorization_evidence or {}
    safe_evidence = {str(k): str(v) for k, v in evidence.items() if k in {"source", "reference", "grant_id"}}
    checks = []
    config = SYNC_ENTITY_REGISTRY.get(event.entity_type)
    if config is None:
        checks.append("UNKNOWN_ENTITY_TYPE")
    if event.operation not in {"create", "insert", "update", "delete"}:
        checks.append("UNSUPPORTED_OPERATION")
    entity = None
    payload = event.payload if isinstance(event.payload, dict) else {}
    dependency_details = resolve_event_dependencies(db, event)
    required = {"workers": {"employee_number", "first_name", "last_name"}, "medical_visits": {"uuid"}}
    missing_payload = sorted(required.get(event.entity_type, set()) - set(payload))
    if missing_payload: checks.append("PAYLOAD_SCHEMA_INVALID")
    if any(not x.get("matched") for x in dependency_details.values() if x.get("required_uuid")):
        checks.append("DEPENDENCY_MISSING")
    if dependency_details["branch"].get("belongs_to_company") is False or dependency_details["drilling_site"].get("belongs_to_branch") is False:
        checks.append("DEPENDENCY_RELATIONSHIP_MISMATCH")
    if config is not None:
        entity = db.scalar(select(config.model).where(config.model.uuid == event.entity_uuid))
        if event.operation in {"update", "delete"} and entity is None: checks.append("TARGET_ENTITY_MISSING")
        if event.operation in {"create", "insert"} and entity is not None: checks.append("CREATE_TARGET_EXISTS")
        # Dependency UUIDs are part of the transport payload when present.  A
        # missing referenced entity is a structural dependency block, kept
        # separate from parent-revision checks and authorization.
        dependency_models = {"companies": Company, "branches": Branch, "drilling_sites": DrillingSite}
        dependency_keys = {"companies": "company_uuid", "branches": "branch_uuid", "drilling_sites": "drilling_site_uuid"}
        for dependency in config.parent_dependencies:
            key = dependency_keys.get(dependency, dependency.removesuffix("s") + "_uuid")
            raw_uuid = payload.get(key)
            # Local journal serializers may carry the relational integer IDs
            # used by WorkerCreate; accept those as the same trusted relation
            # without rewriting the signed event payload.
            legacy_key = {"companies": "company_id", "branches": "branch_id", "drilling_sites": "drilling_site_id"}.get(dependency)
            if raw_uuid is None and legacy_key:
                raw_uuid = payload.get(legacy_key)
            if raw_uuid is None:
                continue
            try:
                dep_uuid = uuid.UUID(str(raw_uuid))
            except (ValueError, TypeError):
                model = dependency_models.get(dependency)
                if model is not None:
                    try:
                        legacy_id = int(raw_uuid)
                    except (TypeError, ValueError):
                        legacy_id = None
                    if legacy_id is not None and db.scalar(select(model).where(model.id == legacy_id)) is not None:
                        continue
                checks.append("DEPENDENCY_UUID_INVALID"); continue
            model = dependency_models.get(dependency)
            if model is not None and db.scalar(select(model).where(model.uuid == dep_uuid)) is None:
                checks.append("DEPENDENCY_MISSING")
    if event.operation in {"update", "delete"} and event.parent_revision_uuid is None:
        checks.append("PARENT_REVISION_REQUIRED")
    if event.parent_revision_uuid is not None:
        parent = db.scalar(select(LocalRevision).where(LocalRevision.revision_uuid == event.parent_revision_uuid))
        if parent is None: checks.append("PARENT_REVISION_MISSING")
        elif parent.entity_type != event.entity_type or parent.entity_uuid != event.entity_uuid: checks.append("PARENT_REVISION_ENTITY_MISMATCH")
    known_revision = event.revision_uuid is not None and db.scalar(select(LocalRevision.revision_uuid).where(LocalRevision.revision_uuid == event.revision_uuid)) is not None
    if known_revision:
        prior_events = db.scalars(select(SyncTransportEvent).where(SyncTransportEvent.revision_uuid == event.revision_uuid, SyncTransportEvent.event_uuid != event.event_uuid, SyncTransportEvent.created_at < event.created_at)).all()
        checks.append("REVISION_CONTENT_MISMATCH" if any(x.content_sha256 != event.content_sha256 for x in prior_events) else "KNOWN_REVISION_DUPLICATE")
    if event.parent_revision_uuid is not None and event.operation in {"update", "delete"}:
        parent_row = db.scalar(select(LocalRevision).where(LocalRevision.revision_uuid == event.parent_revision_uuid))
        if parent_row is not None:
            newer = db.scalar(select(LocalRevision.revision_uuid).where(LocalRevision.entity_type == event.entity_type, LocalRevision.entity_uuid == event.entity_uuid, LocalRevision.local_version > parent_row.local_version, LocalRevision.revision_uuid != event.revision_uuid))
            if newer is not None: checks.append("CONFLICT_COMPETING_BRANCH")
    # Authorization is a separate result and remains blocked: fixture/actor
    # references are not a trusted authorization source.
    auth_status, auth_reason = classify_authorization_evidence(authorization_evidence, event, policy_version=policy_version)
    safe_evidence["authorization"] = {"status": auth_status, "evidence_uuid": evidence.get("evidence_uuid") or safe_evidence.get("reference"), "envelope_sha256": safe_evidence.get("grant_id")}
    structural = checks[0] if checks else None
    reason = structural or auth_reason
    decision = ("blocked_structural" if structural else "blocked_authorization_evidence")
    state = {"entity_exists": entity is not None, "revision_known": known_revision, "structural": checks, "dependencies": dependency_details}
    raw = json.dumps({"event":str(event_uuid),"hash":event.content_sha256,"policy":policy_version,"state":state,"evidence_refs":safe_evidence},sort_keys=True,separators=(",",":"))
    fingerprint = hashlib.sha256(raw.encode()).hexdigest(); now=datetime.now(timezone.utc)
    attempt = db.scalar(select(SyncApplicationAttempt).where(SyncApplicationAttempt.event_uuid==event_uuid, SyncApplicationAttempt.input_fingerprint==fingerprint))
    if attempt is None:
        db.add(SyncApplicationAttempt(event_uuid=event_uuid,content_sha256=event.content_sha256,policy_version=policy_version,input_fingerprint=fingerprint,decision=decision,reason_code=reason,evidence_refs=safe_evidence,evaluated_at=now))
        db.flush()
        if db.info.get("stage5a_fail_after_attempt"):
            raise RuntimeError("STAGE5A_TEST_FAIL_AFTER_ATTEMPT")
    current = db.scalar(select(SyncApplicationDecision).where(SyncApplicationDecision.event_uuid==event_uuid))
    if current is None:
        current=SyncApplicationDecision(event_uuid=event_uuid,content_sha256=event.content_sha256,policy_version=policy_version,input_fingerprint=fingerprint,entity_type=event.entity_type,entity_uuid=event.entity_uuid,decision=decision,reason_code=reason,evidence_refs=safe_evidence,evaluated_at=now); db.add(current)
    elif current.input_fingerprint != fingerprint:
        current.content_sha256=event.content_sha256; current.policy_version=policy_version; current.input_fingerprint=fingerprint; current.decision=decision; current.reason_code=reason; current.evidence_refs=safe_evidence; current.evaluated_at=now
    db.flush()
    if db.info.get("stage5a_fail_before_commit"):
        raise RuntimeError("STAGE5A_TEST_FAIL_BEFORE_COMMIT")
    db.commit(); return current
