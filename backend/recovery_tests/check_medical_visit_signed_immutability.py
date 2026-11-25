"""Internal PostgreSQL check: a validated MedicalVisit rejects incoming edits."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.local_revision import LocalRevision
from app.models.medical_visit import MedicalVisit
from app.models.sync_change import SyncChange
from app.models.user import User
from app.schemas.medical_visit import MedicalVisitValidateRequest
from app.services.entity_application_service import apply_medical_visit_entity, apply_medical_visit_update_entity
from app.services.medical_visit_service import MedicalVisitService
from app.services.permission_service import permission_service
from app.services.auth_service import AuthService
from recovery_tests.check_medical_visit_source_fixture import (
    prepare_medical_visit_source,
    prepare_medical_visit_update_source,
)


def _event(**values):
    return type("IncomingEvent", (), values)()


def main() -> None:
    source_url = os.environ["STAGE5_SOURCE_DB"]
    target_url = os.environ["STAGE5_TARGET_DB"]

    source = prepare_medical_visit_source(source_url)
    update = prepare_medical_visit_update_source(source_url, source)
    target_engine = create_engine(target_url)

    # Establish the unsigned target baseline through the internal application primitive.
    with Session(target_engine) as db:
        worker_uuid = uuid.UUID(str(source.request_payload["worker_uuid"]))
        from app.models.worker import Worker
        worker = db.scalar(select(Worker).where(Worker.uuid == worker_uuid))
        if worker is None:
            raise RuntimeError("TARGET_WORKER_DEPENDENCY_MISSING")
        baseline = _event(
            event_uuid=source.event_uuid,
            operation_uuid=source.operation_uuid,
            entity_uuid=source.visit_uuid,
            revision_uuid=uuid.UUID(str(source.origin_proof["revision_uuid"])),
            payload={**source.request_payload, "worker_uuid": str(worker_uuid)},
        )
        assert apply_medical_visit_entity(db, baseline)["status"] == "applied"
        db.commit()

    # Sign/validate through MedicalVisitService; no status or signature flags are set directly.
    with Session(target_engine) as db:
        visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == source.visit_uuid))
        validator = db.scalar(select(User).where(User.role.in_(("super_admin", "admin", "doctor"))).order_by(User.id))
        if validator is None or "medical_visits.update" not in permission_service.get_effective_permission_codes(validator):
            db.info["sync_bootstrap_mode"] = True
            validator = AuthService().create_platform_user(
                db, "Signed", "Visit", "signed-visit-" + uuid.uuid4().hex[:8] + "@test.local",
                "test-only", "super_admin",
            )
            db.commit()
            db.info.pop("sync_bootstrap_mode", None)
        if visit is None or validator is None:
            raise RuntimeError("SIGNED_VISIT_SETUP_MISSING")
        permission_service.require_permission(validator, "medical_visits.update")
        signed = MedicalVisitService().validate(
            db, visit.id, MedicalVisitValidateRequest(doctor_notes="test validation"),
            validator, int(visit.version), uuid.uuid4(),
        )
        db.commit()
        signed_content = dict(visit.form_data or {})
        signed_version = int(signed.version)

    # The update event is the real source update event.  The immutable guard runs before
    # version/conflict handling, so a signed target is rejected for the documented reason.
    with Session(target_engine) as db:
        before_changes = db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == source.visit_uuid)) or 0
        event = _event(
            event_uuid=update["event_uuid"], operation_uuid=update["operation_uuid"],
            entity_uuid=source.visit_uuid, revision_uuid=uuid.UUID(str(update["origin_proof"]["revision_uuid"])),
            parent_revision_uuid=update["parent_revision_uuid"], base_version=update["base_version"],
            payload=update["update_payload"],
        )
        try:
            apply_medical_visit_update_entity(db, event)
        except ValueError as exc:
            assert str(exc) == "SIGNED_DOCUMENT_IMMUTABLE", str(exc)
            db.rollback()
            rejection = str(exc)
        else:
            raise AssertionError("signed visit update unexpectedly applied")

        db.commit()

    # A fresh session proves the signed record and revision history were unchanged.
    with Session(target_engine) as db:
        row = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == source.visit_uuid))
        revisions = db.scalars(select(LocalRevision).where(LocalRevision.entity_uuid == source.visit_uuid).order_by(LocalRevision.local_version)).all()
        after_changes = db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.entity_uuid == source.visit_uuid)) or 0
        assert row is not None and row.status == "validated" and row.validated_at is not None
        assert int(row.version) == signed_version and dict(row.form_data or {}) == signed_content
        assert len(revisions) == 2 and after_changes == before_changes
        assert "sync_apply_mode" not in db.info
        print("signed_visit=1", "protection_field=status/validated_at", "rejection=" + rejection,
              "content_unchanged=1", "signature_metadata_unchanged=1",
              "version_unchanged=1", "revisions_unchanged=1", "incoming_sync_changes=0",
              "sync_apply_mode_clean=1")


if __name__ == "__main__":
    main()
