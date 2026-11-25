from __future__ import annotations

from pathlib import Path
import uuid as py_uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.installation import require_central_authority, require_installation_capability, require_mobile_device
from app.dependencies.permissions import require_permission
from app.models.mission_session import MissionSession
from app.models.sync_run import SyncRun
from app.models.user import User
from app.schemas.central import (
    CentralApplyRequest,
    CentralBootstrapCompleteRequest,
    CentralBootstrapRequest,
    CentralConflictResolveRequest,
    CentralSyncPushRequest,
)
from app.services.central_sync_service import central_sync_service
from app.services.installation_service import installation_service
from app.utils.responses import success_response

router = APIRouter(prefix="/central", tags=["Central"])
central_sync_router = APIRouter(prefix="/central-sync", tags=["Central Sync"])
system_router = APIRouter(prefix="/system", tags=["System"])


@router.get("/server-info")
def central_server_info(
    _: User = Depends(get_current_user),
    __=Depends(require_central_authority),
    db: Session = Depends(get_db),
):
    return success_response("Central server info", central_sync_service.server_info(db))


@router.get("/capabilities")
def central_capabilities(
    _: User = Depends(get_current_user),
    __=Depends(require_central_authority),
    db: Session = Depends(get_db),
):
    return success_response("Central capabilities", central_sync_service.capabilities(db))


@router.post("/register-device")
def register_device(
    payload: dict,
    _: User = Depends(require_permission("sync.manage_devices")),
    __=Depends(require_installation_capability("manage_registered_devices")),
    db: Session = Depends(get_db),
):
    device = central_sync_service.register_device_secret(
        db,
        device_uuid=py_uuid.UUID(str(payload["device_uuid"])),
        secret=str(payload["device_secret"]),
        app_version=payload.get("app_version"),
        schema_revision=payload.get("schema_revision"),
        protocol_version=str(payload.get("protocol_version") or "1"),
    )
    return success_response("Central device registered", {"device_uuid": str(device.uuid)})


@central_sync_router.get("/readiness")
def central_readiness(
    _: User = Depends(get_current_user),
    __=Depends(require_central_authority),
    db: Session = Depends(get_db),
):
    return success_response("Central sync readiness", central_sync_service.readiness(db))


@central_sync_router.post("/push")
def central_push(
    payload: CentralSyncPushRequest,
    current_user: User = Depends(get_current_user),
    __=Depends(require_central_authority),
    db: Session = Depends(get_db),
    x_central_device_secret: str | None = Header(default=None),
):
    return success_response(
        "Central push processed",
        central_sync_service.push(db, payload, current_user=current_user, central_device_secret=x_central_device_secret),
    )


@central_sync_router.get("/pull")
def central_pull(
    after_central_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("receive_mission_submissions")),
    db: Session = Depends(get_db),
):
    return success_response(
        "Central pull",
        central_sync_service.pull(db, after_central_sequence=after_central_sequence, limit=limit),
    )


@central_sync_router.post("/apply")
def central_apply(
    payload: CentralApplyRequest,
    _: User = Depends(get_current_user),
    __=Depends(require_mobile_device),
    db: Session = Depends(get_db),
):
    state = central_sync_service.apply_central_pull(
        db,
        central_server_uuid=py_uuid.UUID(payload.central_server_uuid),
        central_generation_uuid=py_uuid.UUID(payload.central_generation_uuid),
        changes=payload.changes,
        next_central_sequence=payload.next_central_sequence,
        final_central_sequence=payload.final_central_sequence,
        current_run_uuid=py_uuid.UUID(payload.current_run_uuid) if payload.current_run_uuid else None,
    )
    return success_response(
        "Central pull applied locally",
        {
            "last_pulled_sequence": state.last_pulled_sequence,
            "final_sequence": state.final_mission_sequence,
            "copy_status": state.copy_status,
        },
    )


@central_sync_router.get("/conflicts")
def list_conflicts(
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("resolve_central_conflicts")),
    db: Session = Depends(get_db),
):
    conflicts = central_sync_service.list_conflicts(db)
    return success_response(
        "Central conflicts",
        [
            {
                "uuid": str(item.uuid),
                "mission_uuid": str(item.mission_uuid) if item.mission_uuid else None,
                "entity_type": item.entity_type,
                "entity_uuid": str(item.entity_uuid),
                "incoming_change_uuid": str(item.incoming_change_uuid),
                "source_device_uuid": str(item.source_device_uuid) if item.source_device_uuid else None,
                "source_user_uuid": str(item.source_user_uuid) if item.source_user_uuid else None,
                "mission_sequence": item.mission_sequence,
                "base_version": item.base_version,
                "central_version": item.central_version,
                "conflicting_fields": item.conflicting_fields or [],
                "central_snapshot": item.central_snapshot,
                "mission_snapshot": item.mission_snapshot,
                "status": item.status,
                "resolution_type": item.resolution_type,
                "resolved_payload": item.resolved_payload,
                "resolved_by_user_uuid": str(item.resolved_by_user_uuid) if item.resolved_by_user_uuid else None,
                "resolved_at": item.resolved_at,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in conflicts
        ],
    )


@central_sync_router.get("/conflicts/{conflict_uuid}")
def get_conflict(
    conflict_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("resolve_central_conflicts")),
    db: Session = Depends(get_db),
):
    item = central_sync_service.get_conflict(db, conflict_uuid)
    return success_response(
        "Central conflict",
        {
            "uuid": str(item.uuid),
            "mission_uuid": str(item.mission_uuid) if item.mission_uuid else None,
            "entity_type": item.entity_type,
            "entity_uuid": str(item.entity_uuid),
            "incoming_change_uuid": str(item.incoming_change_uuid),
            "source_device_uuid": str(item.source_device_uuid) if item.source_device_uuid else None,
            "source_user_uuid": str(item.source_user_uuid) if item.source_user_uuid else None,
            "mission_sequence": item.mission_sequence,
            "base_version": item.base_version,
            "central_version": item.central_version,
            "conflicting_fields": item.conflicting_fields or [],
            "central_snapshot": item.central_snapshot,
            "mission_snapshot": item.mission_snapshot,
            "status": item.status,
            "resolution_type": item.resolution_type,
            "resolved_payload": item.resolved_payload,
            "resolved_by_user_uuid": str(item.resolved_by_user_uuid) if item.resolved_by_user_uuid else None,
            "resolved_at": item.resolved_at,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        },
    )


@central_sync_router.post("/conflicts/{conflict_uuid}/resolve")
def resolve_conflict(
    conflict_uuid: py_uuid.UUID,
    payload: CentralConflictResolveRequest,
    current_user: User = Depends(require_permission("sync.resolve_conflicts")),
    __=Depends(require_installation_capability("resolve_central_conflicts")),
    db: Session = Depends(get_db),
):
    conflict = central_sync_service.resolve_conflict(
        db,
        conflict_uuid,
        resolution_type=payload.resolution_type,
        resolved_payload=payload.resolved_payload,
        current_user=current_user,
    )
    return success_response("Conflict resolved", {"uuid": str(conflict.uuid), "status": conflict.status})


@central_sync_router.post("/bootstrap/request")
def bootstrap_request(
    payload: CentralBootstrapRequest,
    current_user: User = Depends(get_current_user),
    __=Depends(require_installation_capability("provide_device_bootstrap")),
    db: Session = Depends(get_db),
):
    bootstrap = central_sync_service.bootstrap_request(
        db,
        device_uuid=py_uuid.UUID(payload.device_uuid),
        allow_overwrite_without_unsent_work=payload.allow_overwrite_without_unsent_work,
    )
    return success_response(
        "Bootstrap requested",
        {"bootstrap_uuid": str(bootstrap.bootstrap_uuid), "status": bootstrap.status, "requested_by": current_user.id},
    )


@central_sync_router.get("/bootstrap/{bootstrap_uuid}/manifest")
def bootstrap_manifest(
    bootstrap_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("provide_device_bootstrap")),
    db: Session = Depends(get_db),
):
    bootstrap = central_sync_service.bootstrap_manifest(db, bootstrap_uuid)
    return success_response("Bootstrap manifest", bootstrap.manifest | {"bootstrap_uuid": str(bootstrap.bootstrap_uuid), "checksum": bootstrap.checksum})


@central_sync_router.get("/bootstrap/{bootstrap_uuid}/download")
def bootstrap_download(
    bootstrap_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("provide_device_bootstrap")),
    db: Session = Depends(get_db),
):
    bootstrap = central_sync_service.bootstrap_manifest(db, bootstrap_uuid)
    return success_response(
        "Bootstrap download",
        {
            "bootstrap_uuid": str(bootstrap.bootstrap_uuid),
            "manifest": bootstrap.manifest,
            "payload": bootstrap.payload,
            "checksum": bootstrap.checksum,
        },
    )


@central_sync_router.post("/bootstrap/{bootstrap_uuid}/complete")
def bootstrap_complete(
    bootstrap_uuid: py_uuid.UUID,
    payload: CentralBootstrapCompleteRequest,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("provide_device_bootstrap")),
    db: Session = Depends(get_db),
):
    bootstrap = central_sync_service.bootstrap_complete(
        db,
        bootstrap_uuid,
        applied_locally=payload.applied_locally,
        notes=payload.notes,
    )
    return success_response("Bootstrap completed", {"bootstrap_uuid": str(bootstrap.bootstrap_uuid), "status": bootstrap.status})


@central_sync_router.get("/submissions")
def list_submissions(
    _: User = Depends(require_permission("sync.view_logs")),
    __=Depends(require_installation_capability("receive_mission_submissions")),
    db: Session = Depends(get_db),
):
    runs = db.scalars(
        select(SyncRun).where(SyncRun.direction == "mission_to_central_push").order_by(SyncRun.started_at.desc().nullslast(), SyncRun.created_at.desc())
    ).all()
    mission_ids = [run.mission_uuid for run in runs if run.mission_uuid is not None]
    missions = {
        mission.uuid: mission
        for mission in db.scalars(select(MissionSession).where(MissionSession.uuid.in_(mission_ids))).all()
    }
    return success_response(
        "Mission submissions",
        [
            {
                "uuid": str(run.uuid),
                "mission_code": missions.get(run.mission_uuid).mission_code if run.mission_uuid in missions else None,
                "mission_server_device": str(run.remote_server_uuid) if run.remote_server_uuid else None,
                "final_mission_sequence": run.cursor_end,
                "submitted_changes": int((run.accepted_count or 0) + (run.conflict_count or 0) + (run.rejected_count or 0) + (run.duplicate_count or 0)),
                "accepted": run.accepted_count,
                "conflicts": run.conflict_count,
                "status": (
                    "Acceptée avec conflits"
                    if run.conflict_count
                    else "Acceptée"
                    if run.status == "completed"
                    else "En cours"
                    if run.status == "running"
                    else "Rejetée"
                    if run.status == "failed"
                    else "En attente"
                ),
            }
            for run in runs
        ],
    )


@system_router.get("/backups")
def list_backups(
    _: User = Depends(require_permission("backups.view")),
    __=Depends(require_installation_capability("create_central_backups")),
    db: Session = Depends(get_db),
):
    status = installation_service.installation_status(db)
    backup_directory = status.get("backup_directory")
    if not backup_directory:
        return success_response("System backups", [])
    root = Path(str(backup_directory))
    if not root.exists():
        return success_response("System backups", [])
    files = sorted([item for item in root.iterdir() if item.is_file()], key=lambda item: item.stat().st_mtime, reverse=True)
    return success_response(
        "System backups",
        [
            {
                "filename": item.name,
                "path": str(item.resolve()),
                "created_at": None,
                "size_bytes": item.stat().st_size,
                "status": "Disponible",
            }
            for item in files
        ],
    )


@system_router.get("/data-integrity")
def data_integrity(
    _: User = Depends(require_permission("sync.view")),
    __=Depends(require_central_authority),
    db: Session = Depends(get_db),
):
    return success_response("Data integrity", central_sync_service.data_integrity(db))
