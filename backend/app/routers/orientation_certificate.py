from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.pagination import PaginationParams
from app.schemas.orientation_certificate import (
    OrientationCertificateCreate,
    OrientationCertificateResponse,
    OrientationCertificateUpdate,
)
from app.schemas.document_pdf import DocumentPdfItem
from app.services.orientation_certificate_pdf_service import OrientationCertificatePdfService
from app.services.orientation_certificate_service import OrientationCertificateService
from app.services.signature_authorization import ensure_can_sign_medical_documents
from app.services.user_signature_service import UserSignatureService
from app.services.workspace_service import WorkspaceService

from app.utils.responses import success_response

router = APIRouter(prefix="/orientation-certificates", tags=["Orientation Certificates"])
pdf_service = OrientationCertificatePdfService()
workspace_service = WorkspaceService()
user_signature_service = UserSignatureService()


def get_orientation_certificate_service(
    db: Session = Depends(get_db),
) -> OrientationCertificateService:
    return OrientationCertificateService(db)


def _ensure_campaign_access(db: Session, current_user: User, campaign_id: int) -> None:
    workspace = workspace_service.get_by_campaign_id(db, campaign_id)
    workspace_service.ensure_access(workspace, current_user)


# ═══════════════════════════════════════════════════════════════
#  STATIC ROUTES FIRST (before any /{certificate_id} routes)
# ═══════════════════════════════════════════════════════════════

@router.get("")
def list_orientation_certificates(
    params: PaginationParams = Depends(get_pagination_params),
    worker_id: int | None = Query(default=None),
    campaign_id: int | None = Query(default=None),
    medical_visit_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    return success_response(
        "Orientation certificates retrieved",
        service.list(
            db,
            params,
            worker_id=worker_id,
            campaign_id=campaign_id,
            medical_visit_id=medical_visit_id,
        ).model_dump(),
    )


@router.get("/worker/{worker_id}", response_model=list[DocumentPdfItem])
def list_worker_orientation_certificates(
    worker_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    items = service.list(db, worker_id=worker_id).items
    return [
        DocumentPdfItem(
            id=item.id,
            date=item.orientation_date,
            doctor=item.doctor_name,
            status=item.status,
            pdf_exists=True,
        )
        for item in items
    ]


@router.get("/workers/{worker_id}/medical-orientations", response_model=list[DocumentPdfItem])
def list_worker_orientation_alias(
    worker_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    items = service.list(db, worker_id=worker_id).items
    return [
        DocumentPdfItem(
            id=item.id,
            date=item.orientation_date,
            doctor=item.doctor_name,
            status=item.status,
            pdf_exists=True,
        )
        for item in items
    ]


@router.get("/last_id")
def get_last_orientation_certificate_id(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    """
    Get the last orientation certificate ID.
    Returns 0 if no certificates exist yet.
    """
    last_id = service.get_last_id(db)
    return success_response(
        "Last orientation certificate ID retrieved",
        {"last_id": last_id},
    )


@router.get("/{certificate_id}/pdf")
def get_orientation_certificate_pdf(
    certificate_id: int,
    include_signature: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get_or_404(certificate_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    if include_signature and not existing.include_workspace_signature:
        ensure_can_sign_medical_documents(current_user)
        user_signature_service.require_uploaded_signature(current_user)
    cached = pdf_service.generate_pdf(
        certificate=existing,
        include_signature=include_signature or bool(existing.include_workspace_signature),
        signature_png=current_user.signature_png,
    )

    filename = f"Attestation-Orientation-{existing.orientation_number}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(cached), media_type="application/pdf", headers=headers)


@router.get("/{certificate_id}/validator-signature")
def get_orientation_certificate_validator_signature(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get_or_404(certificate_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    signature_bytes = user_signature_service.read_signature_bytes(existing.validator_signature_image_path)
    if not signature_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validator signature not found")
    return Response(content=signature_bytes, media_type="image/png")

# ═══════════════════════════════════════════════════════════════
#  DYNAMIC ROUTES AFTER (/{certificate_id} catches everything else)
# ═══════════════════════════════════════════════════════════════

# routers/orientation_certificate.py

@router.get("/{certificate_id}")
def get_orientation_certificate(
    certificate_id: int,
    pdf: bool = Query(False),  # ← add this
    include_signature: bool = Query(False),
    campaign_id: int = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    if pdf:
        # Return PDF instead of JSON
        existing = service.get_or_404(certificate_id)
        _ensure_campaign_access(db, current_user, existing.campaign_id)
        if include_signature and not existing.include_workspace_signature:
            ensure_can_sign_medical_documents(current_user)
            user_signature_service.require_uploaded_signature(current_user)
        pdf_bytes = pdf_service.generate_pdf(
            certificate=existing,
            include_signature=include_signature or bool(existing.include_workspace_signature),
            signature_png=current_user.signature_png,
        )
        filename = f"Attestation-Orientation-{existing.orientation_number}.pdf"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
    
    # Normal JSON response
    item = service.get_or_404(certificate_id)
    _ensure_campaign_access(db, current_user, item.campaign_id)
    return success_response(
        "Orientation certificate retrieved",
        service.to_response(item).model_dump(),
    )

@router.post("", status_code=status.HTTP_201_CREATED)
def create_orientation_certificate(
    request: Request,
    data: OrientationCertificateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    item = service.create(data, current_user=current_user)
    create_audit_log(
        db,
        current_user.id,
        "ORIENTATION_CREATED",
        "orientation_certificate",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response(
        "Orientation certificate created",
        service.to_response(item).model_dump(),
    )


@router.post("/{orientation_id}/print")
def print_orientation_certificate(
    orientation_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get_or_404(orientation_id)
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    item = service.mark_printed(orientation_id)
    create_audit_log(
        db,
        current_user.id,
        "ORIENTATION_PRINTED",
        "orientation_certificate",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response(
        "Orientation certificate marked as printed",
        service.to_response(item).model_dump(),
    )
    
@router.post("/{orientation_id}/sign")
def sign_orientation(
        orientation_id: int,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        service: OrientationCertificateService = Depends(get_orientation_certificate_service),
    ):
        existing = service.get_or_404(orientation_id)

        _ensure_campaign_access(
            db,
            current_user,
            existing.campaign_id,
        )

        item = service.sign_orientation(orientation_id, current_user)

        create_audit_log(
            db,
            current_user.id,
            "ORIENTATION_SIGNED",
            "orientation_certificate",
            item.id,
            request.client.host if request.client else None,
        )

        return success_response(
            "Orientation signed",
            service.to_response(item).model_dump(),
        )

@router.delete("/{certificate_id}") 
def delete_orientation_certificate(
    request: Request,
    certificate_id: int,
    body: PasswordDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get(certificate_id)
    service.delete(certificate_id, password=body.password, current_user=current_user)
    create_audit_log(
        db,
        current_user.id,
        "ORIENTATION_DELETED",
        "orientation_certificate",
        certificate_id,
        request.client.host if request.client else None,
    )
    return success_response("Orientation certificate deleted", {
        "id": existing.id,
        "orientation_number": existing.orientation_number,
        "worker_id": existing.worker_id,
        "campaign_id": existing.campaign_id,
        "doctor_id": existing.doctor_id,
        "status": existing.status,
        "created_at": existing.created_at,
        "updated_at": existing.updated_at,
        "deleted_at": existing.deleted_at,
    })
   
    
    
    
    
    
@router.put("/{certificate_id}")
def update_orientation_certificate(
    request: Request,
    certificate_id: int,
    data: OrientationCertificateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get_or_404(certificate_id)
    update_details = build_update_details(existing, data.model_dump(exclude_unset=True))
    item = service.update(certificate_id, data, current_user=current_user)
    create_audit_log(
        db,
        current_user.id,
        "ORIENTATION_UPDATED",
        "orientation_certificate",
        item.id,
        request.client.host if request.client else None,
    )
    return success_response(
        "Orientation certificate updated",
        service.to_response(item).model_dump(),
    )


@router.delete("/{certificate_id}")
def delete_orientation_certificate(
    request: Request,
    certificate_id: int,
    body: PasswordDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OrientationCertificateService = Depends(get_orientation_certificate_service),
):
    existing = service.get(certificate_id)
    service.delete(certificate_id, password=body.password, current_user=current_user)
    create_audit_log(
        db,
        current_user.id,
        "ORIENTATION_DELETED",
        "orientation_certificate",
        certificate_id,
        request.client.host if request.client else None,
    )
    return success_response("Orientation certificate deleted", {})
