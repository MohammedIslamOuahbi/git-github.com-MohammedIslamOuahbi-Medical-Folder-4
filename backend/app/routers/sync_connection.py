from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.services.sync_connection_service import SyncConnectionService
from app.utils.responses import success_response

router = APIRouter(prefix="/sync", tags=["Sync Connection"])
service = SyncConnectionService()


@router.get("/status")
def get_status(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Sync status retrieved", service.get_status(db).model_dump())


@router.post("/run")
def run_sync(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Sync completed", service.run(db).model_dump())
