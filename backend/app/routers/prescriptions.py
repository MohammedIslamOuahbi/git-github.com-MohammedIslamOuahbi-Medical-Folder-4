from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.prescription import PrescriptionCreate, PrescriptionUpdate
from app.schemas.document_pdf import DocumentPdfItem
from app.services.prescription_service import PrescriptionService
from app.services.document_pdf_storage import DocumentPdfStorage
from app.services.signature_authorization import ensure_can_sign_medical_documents
from app.services.user_signature_service import UserSignatureService
from app.services.workspace_service import WorkspaceService
from app.utils.responses import success_response

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])
service = PrescriptionService()
workspace_service = WorkspaceService()
pdf_storage = DocumentPdfStorage()
user_signature_service = UserSignatureService()


def _ensure_campaign_access(db: Session, current_user: User, campaign_id: int) -> None:
    workspace = workspace_service.get_by_campaign_id(db, campaign_id)
    workspace_service.ensure_access(workspace, current_user)


@router.get("")
def list_prescriptions(
    worker_id: int | None = Query(default=None),
    campaign_id: int | None = Query(default=None),
    medical_visit_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if campaign_id is not None:
        _ensure_campaign_access(db, current_user, campaign_id)
    return success_response(
        "Prescriptions retrieved",
        [
            item.model_dump()
            for item in service.list(
                db,
                worker_id=worker_id,
                campaign_id=campaign_id,
                medical_visit_id=medical_visit_id,
            )
        ],
    )


@router.get("/worker/{worker_id}", response_model=list[DocumentPdfItem])
def list_worker_prescriptions(
    worker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.list(db, worker_id=worker_id)
    if items:
        _ensure_campaign_access(db, current_user, items[0].campaign_id)
    return [
        DocumentPdfItem(
            id=item.id,
            date=str(item.prescription_date),
            doctor=item.doctor_name,
            status=item.status,
            pdf_exists=pdf_storage.exists("prescription", item.id),
        )
        for item in items
    ]


@router.get("/workers/{worker_id}/prescriptions", response_model=list[DocumentPdfItem])
def list_worker_prescriptions_alias(
    worker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.list(db, worker_id=worker_id)
    if items:
        _ensure_campaign_access(db, current_user, items[0].campaign_id)
    return [
        DocumentPdfItem(
            id=item.id,
            date=str(item.prescription_date),
            doctor=item.doctor_name,
            status=item.status,
            pdf_exists=pdf_storage.exists("prescription", item.id),
        )
        for item in items
    ]


@router.get("/{prescription_id}")
def get_prescription(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, item.campaign_id)
    return success_response("Prescription retrieved", service.get_response(db, prescription_id).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_prescription(
    payload: PrescriptionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_campaign_access(db, current_user, payload.campaign_id)
    item = service.create_prescription(db, payload, current_user)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_CREATED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription created", item.model_dump())


@router.put("/{prescription_id}")
def update_prescription(
    prescription_id: int,
    payload: PrescriptionUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    before = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, before.campaign_id)
    details = build_update_details(before, payload.model_dump(exclude_unset=True))
    item = service.update_prescription(db, prescription_id, payload, current_user)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_UPDATED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Prescription updated", item.model_dump())


@router.delete("/{prescription_id}")
def delete_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.delete_prescription(db, prescription_id)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_DELETED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription deleted", item.model_dump())


@router.post("/{prescription_id}/sign")
def sign_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.sign_prescription(db, prescription_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_SIGNED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription signed", item.model_dump())


@router.post("/{prescription_id}/validate")
def validate_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.validate_prescription(db, prescription_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_VALIDATED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription validated", item.model_dump())


@router.post("/{prescription_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.duplicate_prescription(db, prescription_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_DUPLICATED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
        details={"source_prescription_id": prescription_id},
    )
    return success_response("Prescription duplicated", item.model_dump())


@router.post("/{prescription_id}/cancel")
def cancel_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.cancel_prescription(db, prescription_id)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_CANCELLED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription cancelled", item.model_dump())


@router.post("/{prescription_id}/print")
def print_prescription(
    prescription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.print_prescription(db, prescription_id)
    create_audit_log(
        db,
        current_user.id,
        "PRESCRIPTION_PRINTED",
        "prescription",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response("Prescription printed", item.model_dump())


@router.get("/{prescription_id}/pdf")
def get_prescription_pdf(
    prescription_id: int,
    include_signature: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = service.get(db, prescription_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    if include_signature and not existing.include_validator_signature:
        ensure_can_sign_medical_documents(current_user)
        user_signature_service.require_uploaded_signature(current_user)
    cached = pdf_storage.read("prescription", prescription_id)
    if cached is None:
        cached = service.generate_prescription_pdf(
            db,
            prescription_id,
            include_signature=include_signature or existing.include_validator_signature,
            signature_png=current_user.signature_png,
        )
        pdf_storage.write("prescription", prescription_id, cached)
    filename = f'Ordonnance-{existing.prescription_number}.pdf'
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=cached, media_type="application/pdf", headers=headers)


@router.get("/{prescription_id}/preview")
def preview_prescription_pdf(
    prescription_id: int,
    include_signature: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_prescription_pdf(
        prescription_id=prescription_id,
        include_signature=include_signature,
        current_user=current_user,
        db=db,
    )
