from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.audit import create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.import_job import ImportConfirmRequest, ImportFieldMappingRequest, ImportJobRead, ImportRowRead
from app.services.import_service import ImportService
from app.utils.responses import success_response

router = APIRouter(prefix="/imports", tags=["Imports"])
service = ImportService()


@router.post("/upload")
def upload_import(
    request: Request,
    file: UploadFile = File(...),
    campaign_id: int | None = Form(default=None),
    company_id: int | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.upload(
        db,
        file,
        uploaded_by=current_user.id,
        campaign_id=campaign_id,
        company_id=company_id,
    )
    create_audit_log(db, current_user.id, "upload", "import_job", item.id, request.client.host if request and request.client else None)
    return success_response("Import uploaded", ImportJobRead.model_validate(item).model_dump())


@router.get("/{import_job_id}/preview")
def preview_import(import_job_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = service.preview(db, import_job_id)
    return success_response("Import preview retrieved", [ImportRowRead.model_validate(item).model_dump() for item in items])


@router.post("/{import_job_id}/map-fields")
def map_import_fields(import_job_id: int, payload: ImportFieldMappingRequest, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.map_fields(db, import_job_id, payload.mapping)
    return success_response("Import fields mapped", ImportJobRead.model_validate(item).model_dump())


@router.post("/{import_job_id}/validate")
def validate_import(import_job_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.validate(db, import_job_id)
    return success_response("Import validated", ImportJobRead.model_validate(item).model_dump())


@router.post("/{import_job_id}/confirm")
def confirm_import(
    import_job_id: int,
    payload: ImportConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.confirm(db, import_job_id, payload.campaign_id, current_user=current_user)
    return success_response("Import confirmed", ImportJobRead.model_validate(item).model_dump())


@router.get("/history")
def import_history(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = service.history(db)
    return success_response("Import history retrieved", [ImportJobRead.model_validate(item).model_dump() for item in items])
