from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.audit import create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.medicine_import import MedicineImportConfirmRequest, MedicineImportPreviewRequest, MedicineImportUploadResponse
from app.services.medicine_import_service import MedicineImportService
from app.utils.responses import success_response

router = APIRouter(prefix="/medicine-imports", tags=["Medicine Imports"])
service = MedicineImportService()


@router.post("/upload")
def upload_medicine_import(
    request: Request,
    file: UploadFile = File(...),
    source_name: str = Form(default="Ministère de l’Industrie Pharmaceutique"),
    source_version: str | None = Form(default=None),
    import_mode: str = Form(default="preview"),
    notes: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.upload(
        db,
        file,
        current_user=current_user,
        source_name=source_name,
        source_version=source_version,
        import_mode=import_mode,
        notes=notes,
    )
    create_audit_log(
        db,
        current_user.id,
        "MEDICINE_IMPORT_UPLOADED",
        "medicine_import",
        item.id,
        request.client.host if request and request.client else None,
    )
    return success_response("Medicine import uploaded", MedicineImportUploadResponse.model_validate(item).model_dump())


@router.post("/{import_id}/preview")
def preview_medicine_import(
    import_id: int,
    payload: MedicineImportPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medicine import preview retrieved",
        service.preview(db, import_id, current_user=current_user, mapping_override=payload.mapping).model_dump(),
    )


@router.post("/{import_id}/confirm")
def confirm_medicine_import(
    request: Request,
    import_id: int,
    payload: MedicineImportConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.confirm(db, import_id, current_user=current_user, payload=payload)
    create_audit_log(
        db,
        current_user.id,
        "MEDICINE_IMPORT_CONFIRMED",
        "medicine_import",
        item.id,
        request.client.host if request and request.client else None,
    )
    return success_response("Medicine import confirmed", MedicineImportUploadResponse.model_validate(item).model_dump())


@router.post("/{import_id}/cancel")
def cancel_medicine_import(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.cancel(db, import_id, current_user=current_user)
    return success_response("Medicine import cancelled", MedicineImportUploadResponse.model_validate(item).model_dump())


@router.get("")
def list_medicine_imports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.history(db, current_user=current_user)
    return success_response(
        "Medicine import history retrieved",
        [MedicineImportUploadResponse.model_validate(item).model_dump() for item in items],
    )


@router.get("/{import_id}")
def get_medicine_import(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.get(db, import_id, current_user=current_user)
    return success_response("Medicine import retrieved", MedicineImportUploadResponse.model_validate(item).model_dump())


@router.get("/{import_id}/errors")
def list_medicine_import_errors(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.list_errors(db, import_id, current_user=current_user)
    return success_response(
        "Medicine import errors retrieved",
        [item for item in items],
    )


@router.get("/{import_id}/errors/export")
def export_medicine_import_errors(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = service.export_errors_csv(db, import_id, current_user=current_user)
    headers = {"Content-Disposition": f'attachment; filename="medicine-import-errors-{import_id}.csv"'}
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)
