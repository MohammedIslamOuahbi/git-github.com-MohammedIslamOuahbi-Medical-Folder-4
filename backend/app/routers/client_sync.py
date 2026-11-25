from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.services.client_sync_service import ClientSyncService
from app.utils.responses import success_response

router = APIRouter(prefix="/client-sync", tags=["Client Sync"])
service = ClientSyncService()


@router.get("/status")
def get_client_sync_status(
    after_cursor: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return success_response("Client sync status", service.status(db, after_cursor=after_cursor))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export_client_sync_package(
    after_cursor: int = Query(default=0, ge=0),
    limit_per_entity: int = Query(default=1000, ge=1, le=5000),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return success_response(
            "Client sync export generated",
            service.export(db, after_cursor=after_cursor, limit_per_entity=limit_per_entity),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
