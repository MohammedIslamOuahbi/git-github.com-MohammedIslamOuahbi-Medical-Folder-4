from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.services.application_seed_service import ApplicationSeedService
from app.utils.responses import success_response

router = APIRouter(prefix="/bootstrap", tags=["Bootstrap"])
service = ApplicationSeedService()


@router.get("/status")
def get_bootstrap_status(db: Session = Depends(get_db)):
    return success_response("Bootstrap status", service.status(db))
