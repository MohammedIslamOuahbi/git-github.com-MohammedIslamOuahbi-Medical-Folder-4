from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import Response as FastApiResponse
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.aptitude_certificate import (
    AptitudeCertificateCreate,
    AptitudeCertificateResponse,
    AptitudeCertificateUpdate,
)
from app.schemas.document_pdf import DocumentPdfItem
from app.services.aptitude_certificate_pdf_service import AptitudeCertificatePdfService
from app.services.aptitude_certificate_service import AptitudeCertificateService
from app.services.signature_authorization import ensure_can_sign_medical_documents
from app.services.user_signature_service import UserSignatureService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/aptitude-certificates", tags=["aptitude-certificates"])
pdf_service = AptitudeCertificatePdfService()
workspace_service = WorkspaceService()
user_signature_service = UserSignatureService()


def get_service(db: Session = Depends(get_db)) -> AptitudeCertificateService:
    return AptitudeCertificateService(db)


def _ensure_campaign_access(db: Session, current_user: User, campaign_id: int) -> None:
    workspace = workspace_service.get_by_campaign_id(db, campaign_id)
    workspace_service.ensure_access(workspace, current_user)


@router.get("/worker/{worker_id}", response_model=list[DocumentPdfItem])
def list_worker_certificates(
    worker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    from app.services.worker_service import WorkerService

    worker = WorkerService().get(db, worker_id)
    service.ensure_worker_certificate_from_medical_file(worker, current_user.id, current_user=current_user)
    items = service.get_worker_certificates(worker_id)
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


@router.get("/{certificate_id}/pdf")
def get_certificate_pdf(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    certificate = service.get_certificate(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, certificate.campaign_id)
    model = service.get_certificate_model(certificate_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    cached = pdf_service.generate_pdf(
        model,
        include_signature=bool(
            getattr(model, "include_validator_signature", None)
            or getattr(model, "includeWorkspaceSignature", None)
            or getattr(model, "include_workspace_signature", None)
        ),
        signature_png=None,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="aptitude_certificate_{certificate_id}.pdf"'
    }
    return Response(content=cached, media_type="application/pdf", headers=headers)


@router.get("/{certificate_id}/validator-signature")
def get_certificate_validator_signature(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    certificate = service.get_certificate_model(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, certificate.campaign_id)
    signature_bytes = user_signature_service.read_signature_bytes(certificate.validator_signature_image_path)
    if not signature_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validator signature not found")
    return FastApiResponse(content=signature_bytes, media_type="image/png")


@router.get("/", response_model=list[AptitudeCertificateResponse])
def get_all_certificates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _: User = Depends(get_current_user),
    service: AptitudeCertificateService = Depends(get_service),
):
    return service.get_all_certificates(skip, limit)


@router.get("/{certificate_id}", response_model=AptitudeCertificateResponse)
def get_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    certificate = service.get_certificate(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, certificate.campaign_id)
    return certificate


@router.post("/", response_model=AptitudeCertificateResponse, status_code=status.HTTP_201_CREATED)
def create_certificate(
    data: AptitudeCertificateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    _ensure_campaign_access(db, current_user, data.campaign_id)
    return service.create_certificate(data, current_user.id, current_user=current_user)


@router.put("/{certificate_id}", response_model=AptitudeCertificateResponse)
def update_certificate(
    certificate_id: int,
    data: AptitudeCertificateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    existing = service.get_certificate(certificate_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    certificate = service.update_certificate(certificate_id, data, current_user=current_user)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return certificate


@router.post("/{certificate_id}/sign", response_model=AptitudeCertificateResponse)
def sign_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    existing = service.get_certificate(certificate_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    certificate = service.sign_certificate(certificate_id, current_user.id, current_user=current_user)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return certificate


@router.post("/{certificate_id}/print", response_model=AptitudeCertificateResponse)
def print_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    existing = service.get_certificate(certificate_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    certificate = service.print_certificate(certificate_id)
    if not certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return certificate


@router.post("/{certificate_id}/cancel")
def cancel_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    existing = service.get_certificate(certificate_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    ensure_can_sign_medical_documents(current_user)
    success = service.cancel_certificate(certificate_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return {"message": "Certificate cancelled successfully"}


@router.delete("/{certificate_id}")
def delete_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AptitudeCertificateService = Depends(get_service),
):
    existing = service.get_certificate(certificate_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    _ensure_campaign_access(db, current_user, existing.campaign_id)
    ensure_can_sign_medical_documents(current_user)
    success = service.delete_certificate(certificate_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return {"message": "Certificate deleted successfully"}
