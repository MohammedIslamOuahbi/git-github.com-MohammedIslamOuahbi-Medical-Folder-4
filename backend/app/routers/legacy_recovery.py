"""Metadata-only recovery endpoints. No endpoint applies data to medical tables."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.legacy_recovery import RecoveryCaptureRequest
from app.services.legacy_recovery_service import legacy_recovery_service, source_summary
from app.utils.responses import success_response

router = APIRouter(prefix="/recovery", tags=["Recovery"])


@router.post("/sources")
def capture_source(payload: RecoveryCaptureRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = legacy_recovery_service.capture(
        db, user, kind=payload.source_kind, logical_key=payload.logical_key,
        profile_id=payload.profile_id, source_identity=payload.source_identity,
        format_version=payload.format_version, raw_payload=payload.raw_payload, sha256=payload.sha256,
    )
    return success_response("Recovery source captured; medical records were not applied", source_summary(source))


@router.post("/sources/{source_uuid}/resume")
def resume_source(source_uuid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = legacy_recovery_service.resume(db, user, source_uuid)
    return success_response("Recovery item registration resumed", source_summary(source))


@router.get("/sources")
def list_sources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Recovery source metadata", legacy_recovery_service.list_sources(db, user))


@router.get("/sources/{source_uuid}/items")
def list_item_status(source_uuid: uuid.UUID, after: int = Query(default=-1, ge=-1),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Recovery item metadata", legacy_recovery_service.list_item_status(db, user, source_uuid, after))


@router.post("/journals/{table}/capture")
def capture_journal_page(table: str, after_id: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("PostgreSQL journal page captured", legacy_recovery_service.capture_journal_page(
        db, user, table=table, after_id=after_id, limit=limit,
    ))
