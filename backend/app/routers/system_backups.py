from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.dependencies.auth import RestoreAuthorization, get_restore_authorization
from app.dependencies.installation import require_installation_capability
from app.exceptions import ForbiddenException
from app.services.system_backup_service import PostgresBackupService, _delete_file_quietly
from app.utils.responses import success_response

router = APIRouter(prefix="/system-backups", tags=["System Backups"])
service = PostgresBackupService()


def _ensure_local_request(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise ForbiddenException("La restauration de la base est disponible uniquement sur le poste serveur.")


@router.get("/status")
def get_status(
    request: Request,
    auth: RestoreAuthorization = Depends(get_restore_authorization),
    __=Depends(require_installation_capability("create_central_backups")),
):
    del auth
    _ensure_local_request(request)
    return success_response("Statut des sauvegardes systeme recupere.", service.get_status().model_dump())


@router.post("/download")
def download_backup(
    request: Request,
    auth: RestoreAuthorization = Depends(get_restore_authorization),
    __=Depends(require_installation_capability("create_central_backups")),
):
    _ensure_local_request(request)
    artifact = service.create_backup(current_user_id=auth.user_id, current_user_email=auth.email)
    return FileResponse(
        path=str(artifact.path),
        filename=artifact.filename,
        media_type="application/octet-stream",
        background=BackgroundTask(_delete_file_quietly, str(artifact.path)),
    )


@router.post("/restore")
def restore_backup(
    request: Request,
    file: UploadFile = File(...),
    auth: RestoreAuthorization = Depends(get_restore_authorization),
    __=Depends(require_installation_capability("create_central_backups")),
):
    _ensure_local_request(request)
    try:
        response = service.restore_backup(
            upload_filename=file.filename or "backup.dump",
            upload_stream=file.file,
            current_user_id=auth.user_id,
            current_user_email=auth.email,
        )
        return success_response(response.message, response.model_dump())
    finally:
        file.file.close()
