from __future__ import annotations

import base64
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.models.authorization_evidence_record import AuthorizationEvidenceRecord
from app.models.branch import Branch
from app.models.company import Company
from app.models.local_revision import LocalWriteOperation
from app.models.origin_proof import OriginProof
from app.models.proof_pending import OriginProofRequest
from app.models.proof_trust import ProofDelegation, ProofTrustedKey
from app.models.sync_change import SyncChange
from app.models.user import User
from app.models.worker import Worker
from app.schemas.worker import WorkerCreate
from app.services.authorization_evidence_service import issue_for_local_operation, store_local_evidence, verify_authorization_evidence
from app.services.proof_issuer_service import MemoryKeyProvider, ProofIssuerService
from app.services.worker_service import WorkerService
from app.services.proof_verification_service import verify_signature, verify_binding


@dataclass(frozen=True)
class AuthorizedWorkerSourceFixture:
    worker_uuid: uuid.UUID
    operation_uuid: uuid.UUID
    event_uuid: uuid.UUID
    revision_uuid: uuid.UUID
    entity_uuid: uuid.UUID
    user_uuid: uuid.UUID
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    clinic_uuid: uuid.UUID
    content_sha256: str
    policy_version: str
    authorization_evidence: dict[str, Any]
    origin_proof: dict[str, Any]
    authorization_key_id: str
    origin_proof_key_id: str
    authorization_public_key_b64: str
    origin_proof_public_key_b64: str
    authorization_issuer_uuid: uuid.UUID
    origin_service_uuid: uuid.UUID


def _pub(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii")


def prepare_authorized_worker_source(source_url: str, *, source_device_uuid: uuid.UUID,
                                     source_generation_uuid: uuid.UUID,
                                     clinic_uuid: uuid.UUID) -> AuthorizedWorkerSourceFixture:
    engine = create_engine(source_url)
    payload = None
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.role.in_(("super_admin", "admin"))).order_by(User.id))
        company = db.scalar(select(Company))
        if user is None: raise RuntimeError("AUTHORIZED_TEST_USER_NOT_FOUND")
        if company is None: raise RuntimeError("AUTHORIZED_TEST_COMPANY_NOT_FOUND")
        branch = db.scalar(select(Branch).where(Branch.company_id == company.id).order_by(Branch.id))
        if branch is None: raise RuntimeError("AUTHORIZED_TEST_BRANCH_NOT_FOUND")
        operation_uuid = uuid.uuid4()
        payload = WorkerCreate(company_id=company.id, branch_id=branch.id,
            employee_number="AUTH-WORKER-" + uuid.uuid4().hex[:8], national_id="AUTH-NID-" + uuid.uuid4().hex[:8],
            first_name="Authorization", last_name="Worker", gender="other", birth_date=date(1990, 1, 1),
            etat_actual="present", is_active=True)
        db.info.update(sync_source_device_uuid=source_device_uuid,
                       sync_source_generation_uuid=source_generation_uuid,
                       sync_source_clinic_uuid=clinic_uuid)
        created = WorkerService().create(db, payload, user, operation_uuid)
        worker_uuid = created.uuid
        db.commit()

    with Session(engine) as db:
        operation = db.get(LocalWriteOperation, operation_uuid)
        change = db.scalar(select(SyncChange).where(SyncChange.operation_uuid == operation_uuid))
        if operation is None or change is None: raise RuntimeError("AUTHORIZED_WORKER_JOURNAL_EVENT_MISSING")
        if (change.source_device_uuid != source_device_uuid or change.source_generation_uuid != source_generation_uuid
                or change.source_clinic_uuid != clinic_uuid): raise RuntimeError("AUTHORIZED_WORKER_SOURCE_IDENTITY_MISMATCH")
        if change.source_user_uuid is None: raise RuntimeError("AUTHORIZED_WORKER_SOURCE_IDENTITY_INCOMPLETE")
        policy_version = ((operation.result_payload or {}).get("authorization_decision") or {}).get("policy_version")
        if not policy_version: raise RuntimeError("AUTHORIZED_WORKER_POLICY_DECISION_MISSING")
        request = db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid == operation_uuid))
        if request is None or request.policy_version != policy_version: raise RuntimeError("AUTHORIZED_WORKER_PROOF_POLICY_MISMATCH")
        source_user = db.scalar(select(User).where(User.uuid == change.source_user_uuid))
        if source_user is None: raise RuntimeError("AUTHORIZED_WORKER_SOURCE_USER_MISSING")
        db.info.update(sync_source_device_uuid=source_device_uuid,
                       sync_source_generation_uuid=source_generation_uuid,
                       sync_source_clinic_uuid=clinic_uuid)
        replay = WorkerService().create(db, payload, source_user, operation_uuid)
        if replay.uuid != worker_uuid: raise RuntimeError("AUTHORIZED_WORKER_REPLAY_MISMATCH")
        db.commit()

        auth_id, proof_id = "auth-worker-" + uuid.uuid4().hex[:8], "origin-worker-" + uuid.uuid4().hex[:8]
        auth_key, proof_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        auth_authority, origin_service = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        for key_id, key, issuer in ((auth_id, auth_key, auth_authority), (proof_id, proof_key, origin_service)):
            db.add(ProofTrustedKey(key_id=key_id, clinic_uuid=clinic_uuid, origin_service_uuid=issuer,
                origin_device_uuid=source_device_uuid, registration_authority_uuid=auth_authority,
                public_key=_pub(key), algorithm="Ed25519", canonicalization_version="deterministic-json-restricted-v1",
                state="active", registered_at=now))
        scope = f"clinic:{clinic_uuid}:workers:create"
        delegation = uuid.uuid4()
        db.add(ProofDelegation(delegation_uuid=delegation, clinic_uuid=clinic_uuid, origin_service_uuid=origin_service,
            user_uuid=change.source_user_uuid, entity_type=change.entity_type, operation=change.operation,
            policy_version=policy_version, issued_at=now, expires_at=now + timedelta(days=7), state="active",
            authority_ref="authorized-worker-fixture"))
        request.last_reason_code = str(delegation)
        db.flush()
        auth = issue_for_local_operation(db, key_provider=MemoryKeyProvider({auth_id: auth_key}), key_id=auth_id,
            issuer_uuid=auth_authority, issuer_scope=scope, user=source_user, operation=operation, event=change,
            clinic_uuid=clinic_uuid, scope=scope, policy_version=policy_version, permission_code="workers.create")
        store_local_evidence(db, auth)
        proof = ProofIssuerService(MemoryKeyProvider({proof_id: proof_key}), key_id=proof_id).issue(db, request_uuid=request.request_uuid)
        db.commit()

    with Session(engine) as db:
        operation = db.get(LocalWriteOperation, operation_uuid)
        change = db.scalar(select(SyncChange).where(SyncChange.operation_uuid == operation_uuid))
        auth_row = db.scalar(select(AuthorizationEvidenceRecord).where(AuthorizationEvidenceRecord.operation_uuid == operation_uuid))
        proof_row = db.scalar(select(OriginProof).where(OriginProof.event_uuid == change.change_uuid))
        if not operation or not change or not auth_row or not proof_row: raise RuntimeError("AUTHORIZED_WORKER_PROOFS_NOT_PERSISTED")
        expected = {"subject_user_uuid": str(change.source_user_uuid), "operation_uuid": str(operation_uuid),
            "event_uuid": str(change.change_uuid), "entity_type": change.entity_type, "entity_uuid": str(change.entity_uuid),
            "content_sha256": change.content_sha256, "clinic_uuid": str(clinic_uuid), "scope": auth["scope"],
            "policy_version": policy_version}
        status, reason = verify_authorization_evidence(auth, public_key_b64=_pub(auth_key), expected=expected,
            trusted_issuer_uuid=auth_authority, trusted_issuer_scope=auth["scope"])
        if status != "accepted_test_only": raise RuntimeError(f"AUTHORIZATION_VERIFY_FAILED:{reason}")
        if proof_row.proof != proof or proof.get("event_uuid") != str(change.change_uuid) or proof.get("operation_uuid") != str(operation_uuid):
            raise RuntimeError("ORIGIN_PROOF_BINDING_MISMATCH")
        if verify_signature(proof, _pub(proof_key)) != "valid" or verify_binding(
            proof, event_uuid=str(change.change_uuid), operation_uuid=str(operation_uuid),
            content_sha256=change.content_sha256, entity_uuid=str(change.entity_uuid),
        ) != "valid":
            raise RuntimeError("ORIGIN_PROOF_VERIFY_FAILED")
        return AuthorizedWorkerSourceFixture(worker_uuid=uuid.UUID(str(worker_uuid)), operation_uuid=operation_uuid,
            event_uuid=change.change_uuid, revision_uuid=change.revision_uuid, entity_uuid=change.entity_uuid,
            user_uuid=change.source_user_uuid, source_device_uuid=source_device_uuid, source_generation_uuid=source_generation_uuid,
            clinic_uuid=clinic_uuid, content_sha256=change.content_sha256, policy_version=policy_version,
            authorization_evidence=dict(auth), origin_proof=dict(proof), authorization_key_id=auth_id,
            origin_proof_key_id=proof_id, authorization_public_key_b64=_pub(auth_key), origin_proof_public_key_b64=_pub(proof_key),
            authorization_issuer_uuid=auth_authority, origin_service_uuid=origin_service)


def main() -> None:
    source_url = os.environ["WORKER_TEST_DB"]
    fixture = prepare_authorized_worker_source(source_url,
        source_device_uuid=uuid.UUID(os.environ.get("WORKER_SOURCE_DEVICE_UUID", str(uuid.uuid4()))),
        source_generation_uuid=uuid.UUID(os.environ.get("WORKER_SOURCE_GENERATION_UUID", str(uuid.uuid4()))),
        clinic_uuid=uuid.UUID(os.environ.get("WORKER_SOURCE_CLINIC_UUID", str(uuid.uuid4()))))
    with Session(create_engine(source_url)) as db:
        assert db.scalar(select(Worker).where(Worker.uuid == fixture.worker_uuid))
        assert db.scalar(select(func.count(SyncChange.id)).where(SyncChange.operation_uuid == fixture.operation_uuid)) == 1
    print("worker_created=1\nreplay_same_worker=1\nno_duplicate_change=1\nauthorization_signature_valid=1\norigin_proof_signature_valid=1\nbindings_match=1\nfresh_session_persisted=1")


if __name__ == "__main__":
    main()
