from __future__ import annotations

from fastapi import APIRouter, Depends, Response, Query, Header
import uuid
from sqlalchemy import select
from app.models.local_revision import LocalEditAttempt
from app.models.medical_visit import MedicalVisit
from app.exceptions import ForbiddenException, NotFoundException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.medical_visit import (
    MedicalVisitCreate,
    MedicalVisitDuplicateRequest,
    MedicalVisitStatusUpdate,
    MedicalVisitUpdate,
    MedicalVisitValidateRequest,
)
from app.schemas.aptitude_certificate import AptitudeCertificateUpdate
from app.services.medical_visit_service import MedicalVisitService
from app.services.document_pdf_storage import DocumentPdfStorage
from app.services.aptitude_certificate_service import AptitudeCertificateService
from app.services.worker_medical_visit_pdf_service import WorkerMedicalVisitPdfService
from app.services.workspace_service import WorkspaceService
from app.utils.responses import success_response

router = APIRouter(prefix="/medical-visits", tags=["Medical Visits"])
service = MedicalVisitService()
pdf_service = WorkerMedicalVisitPdfService()
pdf_storage = DocumentPdfStorage()
workspace_service = WorkspaceService()


def _ensure_visit_access(db: Session, current_user: User, visit_id: int) -> None:
    visit = service.get(db, visit_id)
    if visit.campaign_id is None:
        return
    workspace = workspace_service.get_by_campaign_id(db, visit.campaign_id)
    workspace_service.ensure_access(workspace, current_user)


@router.get("/edit-attempts/{attempt_uuid}")
def get_edit_attempt(attempt_uuid: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = db.get(LocalEditAttempt, attempt_uuid)
    if attempt is None or attempt.entity_type != "medical_visits":
        raise NotFoundException("EDIT_ATTEMPT_NOT_FOUND")
    if attempt.actor_user_uuid != current_user.uuid or not current_user.is_active:
        raise ForbiddenException("EDIT_ATTEMPT_ACCESS_DENIED")
    visit = db.scalar(select(MedicalVisit).where(MedicalVisit.uuid == attempt.entity_uuid))
    if visit is None:
        raise NotFoundException("Medical visit not found")
    _ensure_visit_access(db, current_user, visit.id)
    return success_response("Preserved edit attempt", {
        "operation_uuid": str(attempt.operation_uuid), "expected_version": attempt.expected_version,
        "observed_version": attempt.observed_version, "reason_code": attempt.reason_code,
        "attempted_payload": attempt.attempted_payload, "created_at": attempt.created_at,
    })


@router.post("")
def create_visit(payload: MedicalVisitCreate,
                 operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                 current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Medical visit created", service.create(db, payload, current_user, operation_uuid).model_dump())


@router.post("/workers/{worker_id}/medical-visits/{visit_id}/duplicate")
def duplicate_visit(
    worker_id: int,
    visit_id: int,
    payload: MedicalVisitDuplicateRequest,
    operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medical visit duplicated",
        service.duplicate(db, worker_id, visit_id, payload, current_user, operation_uuid).model_dump(),
    )


@router.get("/{visit_id}")
def get_visit(visit_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Medical visit retrieved", service.get(db, visit_id).model_dump())


@router.get("/{visit_id}/pdf")
def get_visit_pdf(
    visit_id: int,
    campaign_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = service._get(db, visit_id)
    worker = visit.worker
    workspace_settings = None
    if campaign_id is not None:
        workspace = workspace_service.get_by_campaign_id(db, campaign_id)
        workspace_service.ensure_access(workspace, current_user)
        workspace_settings = workspace.settings_json or {}
    cached = pdf_storage.read("medical-visit", visit_id)
    if cached is None:
        cached = pdf_service.generate_pdf(
            worker,
            workspace_settings=workspace_settings,
            signature_png=current_user.signature_png,
            visit_id=visit_id,
            form_data=visit.form_data,
        )
        pdf_storage.write("medical-visit", visit_id, cached)
    headers = {"Content-Disposition": 'attachment; filename="Fich intern de visit Medicale.pdf"'}
    return Response(content=cached, media_type="application/pdf", headers=headers)


@router.get("/{visit_id}/test-results")
def get_visit_test_results(visit_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Visit test results retrieved", service.get_test_results(db, visit_id))


@router.post("/{visit_id}/test-results")
def save_visit_test_results(visit_id: int, payload: dict,
                            expected_version: int = Header(alias="X-Expected-Version", ge=1),
                            operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                            current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    return success_response("Visit test results saved", service.save_test_results(db, visit_id, payload, current_user, expected_version, operation_uuid).model_dump())


@router.get("/workers/{worker_id}/visits")
def list_worker_visits(worker_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker visits retrieved", [item.model_dump() for item in service.list_by_worker(db, worker_id)])


@router.patch("/{visit_id}")
def update_visit(visit_id: int, payload: MedicalVisitUpdate,
                 expected_version: int = Header(alias="X-Expected-Version", ge=1),
                 operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                 current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    return success_response("Medical visit updated", service.update(db, visit_id, payload, current_user, expected_version, operation_uuid).model_dump())


@router.patch("/{visit_id}/status")
def update_visit_status(visit_id: int, payload: MedicalVisitStatusUpdate,
                        expected_version: int = Header(alias="X-Expected-Version", ge=1),
                        operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    return success_response("Medical visit status updated", service.update_status(db, visit_id, payload, current_user, expected_version, operation_uuid).model_dump())


@router.post("/{visit_id}/validate")
def validate_visit(visit_id: int, payload: MedicalVisitValidateRequest,
                   expected_version: int = Header(alias="X-Expected-Version", ge=1),
                   operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                   current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    return success_response("Medical visit validated", service.validate(db, visit_id, payload, current_user, expected_version, operation_uuid).model_dump())


@router.post("/{visit_id}/reopen")
def reopen_visit(visit_id: int,
                 expected_version: int = Header(alias="X-Expected-Version", ge=1),
                 operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                 current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    return success_response("Medical visit reopened", service.reopen(db, visit_id, current_user, expected_version, operation_uuid).model_dump())


@router.get("/{visit_id}/edit-attempts")
def list_own_edit_attempts(visit_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_visit_access(db, current_user, visit_id)
    visit = service._get(db, visit_id)
    rows = db.scalars(select(LocalEditAttempt).where(
        LocalEditAttempt.entity_type == "medical_visits", LocalEditAttempt.entity_uuid == visit.uuid,
        LocalEditAttempt.actor_user_uuid == current_user.uuid,
    ).order_by(LocalEditAttempt.created_at.desc()).limit(100)).all()
    return success_response("Own preserved edit attempts", [{
        "operation_uuid": str(row.operation_uuid), "expected_version": row.expected_version,
        "observed_version": row.observed_version, "reason_code": row.reason_code,
        "attempted_payload": row.attempted_payload, "created_at": row.created_at,
    } for row in rows])


@router.get("/{visit_id}/aptitude-certificate")
def get_visit_aptitude_certificate(
    visit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_visit_access(db, current_user, visit_id)
    certificate = AptitudeCertificateService(db).get_or_create_for_visit(visit_id, current_user=current_user)
    return success_response("Aptitude certificate retrieved", certificate.model_dump())


@router.put("/{visit_id}/aptitude-certificate")
def update_visit_aptitude_certificate(
    visit_id: int,
    payload: AptitudeCertificateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_visit_access(db, current_user, visit_id)
    certificate = AptitudeCertificateService(db).update_for_visit(
        visit_id,
        payload,
        current_user=current_user,
    )
    return success_response("Aptitude certificate updated", certificate.model_dump())


@router.post("/{visit_id}/aptitude-certificate/validate")
def validate_visit_aptitude_certificate(
    visit_id: int,
    payload: AptitudeCertificateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_visit_access(db, current_user, visit_id)
    certificate = AptitudeCertificateService(db).validate_for_visit(
        visit_id,
        payload,
        current_user=current_user,
    )
    return success_response("Aptitude certificate validated", certificate.model_dump())


@router.delete("/{visit_id}/aptitude-certificate")
def delete_visit_aptitude_certificate(
    visit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_visit_access(db, current_user, visit_id)
    deleted = AptitudeCertificateService(db).delete_for_visit(visit_id, current_user=current_user)
    if not deleted:
        return success_response("Aptitude certificate already absent", {"deleted": False})
    return success_response("Aptitude certificate deleted", {"deleted": True})
