from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status, Header
import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_permission
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.local_revision import LocalEditAttempt
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.pagination import PaginationParams
from app.schemas.worker import WorkerCreate, WorkerRead, WorkerUpdate
from app.schemas.medical_visit import MedicalVisitDuplicateRequest
from app.services.worker_medical_dossier_pdf_service import WorkerMedicalDossierPdfService
from app.services.document_pdf_storage import DocumentPdfStorage
from app.services.aptitude_certificate_service import AptitudeCertificateService
from app.services.aptitude_certificate_pdf_service import AptitudeCertificatePdfService
from app.services.workspace_service import WorkspaceService
from app.services.worker_medical_visit_pdf_service import WorkerMedicalVisitPdfService
from app.services.medical_visit_service import MedicalVisitService
from app.services.worker_service import WorkerService
from app.schemas.document_pdf import DocumentPdfItem
from app.utils.responses import success_response

router = APIRouter(prefix="/workers", tags=["Workers"])
service = WorkerService()
pdf_service = WorkerMedicalVisitPdfService()
dossier_pdf_service = WorkerMedicalDossierPdfService()
pdf_storage = DocumentPdfStorage()
aptitude_pdf_service = AptitudeCertificatePdfService()
workspace_service = WorkspaceService()
medical_visit_service = MedicalVisitService()

from sqlalchemy import desc
from app.models.worker import Worker


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


@router.get("/edit-attempts/{attempt_uuid}")
def get_own_worker_edit_attempt(attempt_uuid: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = db.get(LocalEditAttempt, attempt_uuid)
    if attempt is None or attempt.entity_type != "workers":
        raise NotFoundException("EDIT_ATTEMPT_NOT_FOUND")
    if not current_user.is_active or attempt.actor_user_uuid != current_user.uuid:
        raise ForbiddenException("EDIT_ATTEMPT_ACCESS_DENIED")
    return success_response("Preserved worker edit attempt", {
        "operation_uuid": str(attempt.operation_uuid), "expected_version": attempt.expected_version,
        "observed_version": attempt.observed_version, "reason_code": attempt.reason_code,
        "attempted_payload": attempt.attempted_payload, "created_at": attempt.created_at,
    })

    
@router.get("")
def list_workers(params: PaginationParams = Depends(get_pagination_params), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Workers retrieved", service.list(db, params).model_dump())

# router/worker.py
@router.get("/last_id")
def get_last_worker_id(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("Getting last worker ID",{"last_id": service.get_last_id(db)})
    return success_response("Last worker ID retrieved", {"last_id": service.get_last_id(db)})


@router.get("/lookup")
def lookup_worker(
    first_name: str = Query(...),
    last_name: str = Query(...),
    birth_date: str = Query(...),
    national_id: str = Query(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import date

    if not all([first_name.strip(), last_name.strip(), birth_date.strip(), national_id.strip()]):
        raise BadRequestException("All lookup parameters are required")

    parsed_birth_date = date.fromisoformat(birth_date.strip())
    worker = service.lookup(
        db,
        normalize_text(first_name),
        normalize_text(last_name),
        parsed_birth_date,
        national_id.strip(),
    )
    return success_response("Worker retrieved", WorkerRead.model_validate(worker).model_dump())


@router.get("/lookup-with-history")
def lookup_worker_with_history(
    first_name: str = Query(...),
    last_name: str = Query(...),
    birth_date: str = Query(...),
    national_id: str = Query(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import date

    if not all([first_name.strip(), last_name.strip(), birth_date.strip(), national_id.strip()]):
        raise BadRequestException("All lookup parameters are required")

    parsed_birth_date = date.fromisoformat(birth_date.strip())
    result = service.lookup_with_history(
        db,
        normalize_text(first_name),
        normalize_text(last_name),
        parsed_birth_date,
        national_id.strip(),
    )
    return success_response(
        "Worker retrieved",
        {
            "worker": WorkerRead.model_validate(result["worker"]).model_dump(),
            "history": result["history"],
        },
    )



@router.post("", status_code=status.HTTP_201_CREATED)
def create_worker(payload: WorkerCreate, request: Request,
                  operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                  current_user: User = Depends(require_permission("workers.create")), db: Session = Depends(get_db)):
    try:
        item = service.create(db, payload, current_user, operation_uuid)
    except IntegrityError:
        db.rollback()
        raise BadRequestException("National identity number already exists.")
    if not db.info.get("local_write_replay"):
        create_audit_log(
            db,
            current_user.id,
            "create",
            "worker",
            item.id,
            request.client.host if request.client else None,
            worker_id=item.id,
        )
    return success_response("Worker created", WorkerRead.model_validate(item).model_dump())


@router.get("/{worker_id}")
def get_worker(worker_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker retrieved", WorkerRead.model_validate(service.get(db, worker_id)).model_dump())


@router.put("/{worker_id}")
def update_worker(worker_id: int, payload: WorkerUpdate, request: Request,
                  expected_version: int = Header(alias="X-Expected-Version", ge=1),
                  operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, worker_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    try:
        item = service.update(db, worker_id, payload, current_user, expected_version, operation_uuid)
    except IntegrityError:
        db.rollback()
        raise BadRequestException("National identity number already exists.")
    if not db.info.get("local_write_replay"):
        create_audit_log(
            db,
            current_user.id,
            "update",
            "worker",
            item.id,
            request.client.host if request.client else None,
            details=details,
            worker_id=item.id,
        )
    return success_response("Worker updated", WorkerRead.model_validate(item).model_dump())


@router.delete("/{worker_id}")
def delete_worker(worker_id: int, payload: PasswordDeleteRequest, request: Request,
                  expected_version: int = Header(alias="X-Expected-Version", ge=1),
                  operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.delete(db, worker_id, current_user, payload.password, expected_version, operation_uuid)
    if not db.info.get("local_write_replay"):
        create_audit_log(
            db,
            current_user.id,
            "delete",
            "worker",
            item.id,
            request.client.host if request.client else None,
            worker_id=item.id,
        )
    return success_response("Worker deleted", WorkerRead.model_validate(item).model_dump())


@router.get("/{worker_id}/tests")
def get_worker_tests(worker_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker tests retrieved", [item.id for item in service.tests(db, worker_id)])


@router.get("/{worker_id}/campaigns")
def get_worker_campaigns(worker_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker campaigns retrieved", [item.id for item in service.campaigns(db, worker_id)])


@router.get("/{worker_id}/visits")
def get_worker_visits(worker_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.medical_visit_service import MedicalVisitService

    visit_service = MedicalVisitService()
    return success_response("Worker visits retrieved", [item.model_dump() for item in visit_service.list_by_worker(db, worker_id)])


@router.post("/{worker_id}/medical-visits/{visit_id}/duplicate")
def duplicate_worker_visit(
    worker_id: int,
    visit_id: int,
    payload: MedicalVisitDuplicateRequest,
    operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medical visit duplicated",
        medical_visit_service.duplicate(db, worker_id, visit_id, payload, current_user, operation_uuid).model_dump(),
    )


@router.get("/{worker_id}/medical-visit-pdf")
def download_worker_medical_visit_pdf(
    worker_id: int,
    campaign_id: int | None = Query(default=None),
    visit_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    worker = service.get(db, worker_id)
    visit = None
    if visit_id is not None:
        visit = medical_visit_service.get(db, visit_id)
        if visit.worker_id != worker.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical visit not found")
    workspace_settings = None
    if campaign_id is not None:
        workspace = workspace_service.get_by_campaign_id(db, campaign_id)
        workspace_service.ensure_access(workspace, current_user)
        workspace_settings = workspace.settings_json or {}
    pdf_bytes = pdf_service.generate_pdf(
        worker,
        workspace_settings=workspace_settings,
        signature_png=current_user.signature_png,
        visit_id=visit_id,
        form_data=visit.form_data if visit is not None else None,
    )
    filename = "Fich intern de visit Medicale.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/{worker_id}/medical-dossier-pdf")
def download_worker_medical_dossier_pdf(
    worker_id: int,
    campaign_id: int | None = Query(default=None),
    visit_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    worker = service.get(db, worker_id)
    workspace_settings = None
    if campaign_id is not None:
        workspace = workspace_service.get_by_campaign_id(db, campaign_id)
        workspace_service.ensure_access(workspace, current_user)
        workspace_settings = workspace.settings_json or {}
    pdf_bytes = dossier_pdf_service.generate_pdf(
        worker,
        workspace_settings=workspace_settings,
        signature_png=current_user.signature_png,
        visit_id=visit_id,
    )
    filename = "Dossier médical.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/{worker_id}/medical-file/pdf")
def get_worker_medical_file_pdf(
    worker_id: int,
    campaign_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    worker = service.get(db, worker_id)
    if campaign_id is not None:
        workspace = workspace_service.get_by_campaign_id(db, campaign_id)
        workspace_service.ensure_access(workspace, current_user)
        workspace_settings = workspace.settings_json or {}
    else:
        workspace_settings = None
    cached = pdf_storage.read("medical-file", worker_id)
    if cached is None:
        cached = dossier_pdf_service.generate_pdf(
            worker,
            workspace_settings=workspace_settings,
            signature_png=current_user.signature_png,
        )
        pdf_storage.write("medical-file", worker_id, cached)
    headers = {"Content-Disposition": 'attachment; filename="Dossier medical.pdf"'}
    return Response(content=cached, media_type="application/pdf", headers=headers)


@router.get("/{worker_id}/aptitude-certificates", response_model=list[DocumentPdfItem])
def list_worker_aptitude_certificates(
    worker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    worker = service.get(db, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    service_impl = AptitudeCertificateService(db)
    service_impl.ensure_worker_certificate_from_medical_file(worker, current_user.id, current_user=current_user)
    items = service_impl.get_worker_certificates(worker_id)
    return [
        DocumentPdfItem(
            id=item.id,
            date=item.issue_date,
            doctor=item.doctor_name,
            status=item.status,
            pdf_exists=pdf_storage.exists("aptitude-certificate", item.id),
        )
        for item in items
    ]


@router.get("/aptitude-certificates/{certificate_id}/pdf")
def download_aptitude_certificate_pdf(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service_impl = AptitudeCertificateService(db)
    certificate = service_impl.repository.get_by_id(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    workspace = workspace_service.get_by_campaign_id(db, certificate.campaign_id)
    workspace_service.ensure_access(workspace, current_user)

    cached = pdf_storage.read("aptitude-certificate", certificate_id)
    if cached is None:
        cached = aptitude_pdf_service.generate_pdf(
            certificate,
            include_signature=certificate.include_workspace_signature,
            signature_png=current_user.signature_png,
        )
        pdf_storage.write("aptitude-certificate", certificate_id, cached)

    filename = f'Certificat-d-aptitude-{certificate.certificate_number}.pdf'
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=cached, media_type="application/pdf", headers=headers)
