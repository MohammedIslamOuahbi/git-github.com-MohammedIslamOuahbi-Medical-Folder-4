from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.installation import require_installation_capability
from app.models.sync_device import SyncDevice
from app.models.user import User
from app.schemas.sync import (
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncResolveConflictRequest,
    SyncStatusResponse,
)
from app.services.sync_service import SyncService
from app.services.sync_connection_service import SyncConnectionService
from app.utils.responses import success_response

router = APIRouter(prefix="/sync", tags=["Sync"])
service = SyncService()
connection_service = SyncConnectionService()


@router.post("/push")
def push_changes(payload: SyncPushRequest, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Sync push completed", service.push(db, payload).model_dump())


@router.get("/pull")
def pull_changes(
    device_id: str = Query(...),
    last_sync_at: str | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response("Sync pull completed", service.pull(db, device_id=device_id, last_sync_at=last_sync_at).model_dump())


@router.post("/resolve-conflict")
def resolve_conflict(payload: SyncResolveConflictRequest, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Conflict resolved", service.resolve_conflict(db, payload))


@router.get("/status")
def get_sync_status(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Sync status retrieved", service.status(db).model_dump())


@router.post("/run")
def run_sync(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Sync completed", connection_service.run(db).model_dump())


@router.get("/devices")
def list_registered_devices(
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("manage_registered_devices")),
    db: Session = Depends(get_db),
):
    devices = db.scalars(select(SyncDevice).order_by(SyncDevice.last_seen_at.desc().nullslast(), SyncDevice.registered_at.desc())).all()
    return success_response(
        "Registered devices",
        [
            {
                "uuid": str(device.uuid),
                "name": device.device_name,
                "code": device.device_code,
                "last_connection_at": device.last_seen_at,
                "last_sync_at": device.last_central_sync_at or device.last_mission_sync_at,
                "version": device.app_version,
                "schema_revision": device.schema_revision,
                "status": "Actif" if device.is_active and not device.is_revoked else "Révoqué",
                "revoked": device.is_revoked,
            }
            for device in devices
        ],
    )
