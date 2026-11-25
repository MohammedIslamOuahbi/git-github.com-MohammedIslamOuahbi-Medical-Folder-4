from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.permissions import require_permission
from app.dependencies.installation import require_installation_capability
from app.models.user import User
from app.schemas.sync_connection import BackupRestoreRequest
from app.services.backup_service import BackupService
from app.utils.responses import success_response

router = APIRouter(prefix="/backup", tags=["Backup"])
service = BackupService()


@router.get("/status")
def get_status(
    _: User = Depends(require_permission("backups.view")),
    __=Depends(require_installation_capability("create_central_backups")),
    db: Session = Depends(get_db),
):
    return success_response("Backup status retrieved", service.status(db).model_dump())


@router.post("/create")
def create_backup(
    current_user: User = Depends(require_permission("backups.create")),
    __=Depends(require_installation_capability("create_central_backups")),
    db: Session = Depends(get_db),
):
    return success_response("Backup created", service.create_backup(db).model_dump())


@router.post("/restore")
def restore_backup(
    payload: BackupRestoreRequest,
    current_user: User = Depends(require_permission("backups.restore")),
    __=Depends(require_installation_capability("create_central_backups")),
    db: Session = Depends(get_db),
):
    return success_response("Backup restored", service.restore_backup(db, payload.backup_path).model_dump())


@router.post("/export-usb")
def export_backup(
    current_user: User = Depends(require_permission("backups.download")),
    __=Depends(require_installation_capability("create_central_backups")),
    db: Session = Depends(get_db),
):
    return success_response("Backup exported", service.export_to_usb(db).model_dump())
