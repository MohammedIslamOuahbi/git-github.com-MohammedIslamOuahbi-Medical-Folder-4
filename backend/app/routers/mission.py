from __future__ import annotations

import uuid as py_uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.installation import require_installation_capability, require_mobile_device
from app.dependencies.permissions import require_permission
from app.core.enums import ConnectionMode
from app.models.device_sync_state import DeviceSyncState
from app.models.user import User
from app.schemas.mission import ConnectionModeUpdateRequest, MissionCopyApplyRequest, MissionJoinRequest, MissionSessionCreateRequest, RuntimeSwitchRequest
from app.schemas.mission import DeviceCurrentUpdateRequest
from app.services.mission_copy_service import mission_copy_service
from app.services.mission_service import mission_service
from app.services.permission_service import permission_service
from app.services.connection_mode_service import connection_mode_service
from app.core.audit import create_audit_log
from app.utils.responses import success_response

router = APIRouter(prefix="/mission", tags=["Mission"])
mission_sync_router = APIRouter(prefix="/mission-sync", tags=["Mission Sync"])
runtime_router = APIRouter(prefix="/runtime", tags=["Runtime"])
device_router = APIRouter(prefix="/device", tags=["Device"])


@router.get("/server-info")
def server_info(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Mission server info", mission_service.server_info(db))


@device_router.get("/current")
def get_current_device(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Current device", mission_service.current_device(db))


@device_router.patch("/current")
def update_current_device(
    payload: DeviceCurrentUpdateRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response("Current device updated", mission_service.update_current_device(db, device_name=payload.device_name))


@router.post("/sessions")
def create_session(
    payload: MissionSessionCreateRequest,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("local_network.start_server")),
    db: Session = Depends(get_db),
):
    mission = mission_service.create_session(db, payload, current_user)
    return success_response("Mission session created", {"uuid": str(mission.uuid), "status": mission.status})


@router.get("/sessions/current")
def current_session(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mission = mission_service.current_session(db)
    return success_response(
        "Current mission session",
        None
        if mission is None
        else {
            "uuid": str(mission.uuid),
            "mission_code": mission.mission_code,
            "mission_name": mission.mission_name,
            "status": mission.status,
            "mission_current_sequence": mission.mission_current_sequence,
        },
    )


@router.post("/sessions/{mission_uuid}/activate")
def activate_session(
    mission_uuid: py_uuid.UUID,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("local_network.start_server")),
    db: Session = Depends(get_db),
):
    mission = mission_service.activate_session(db, mission_uuid, current_user)
    return success_response("Mission session activated", {"uuid": str(mission.uuid), "status": mission.status})


@router.post("/sessions/{mission_uuid}/abort")
def abort_session(
    mission_uuid: py_uuid.UUID,
    payload: RuntimeSwitchRequest,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("local_network.stop_server")),
    db: Session = Depends(get_db),
):
    mission = mission_service.abort_session(db, mission_uuid, current_user, reason=payload.reason)
    return success_response("Mission session aborted", {"uuid": str(mission.uuid), "status": mission.status})


@router.post("/sessions/{mission_uuid}/join")
def join_session(
    mission_uuid: py_uuid.UUID,
    payload: MissionJoinRequest,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("run_mission_client")),
    db: Session = Depends(get_db),
):
    result = mission_service.join_session(db, mission_uuid, payload)
    return success_response(
        "Mission session joined",
        {
            "credential": result["credential"],
            "participant": {
                "device_uuid": str(result["participant"].device_uuid),
                "status": result["participant"].status,
            },
        },
    )


@router.get("/sessions/{mission_uuid}/devices")
def list_devices(
    mission_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_mobile_device),
    db: Session = Depends(get_db),
):
    devices = mission_service.list_devices(db, mission_uuid)
    return success_response(
        "Mission devices",
        [
            {
                "mission_session_uuid": str(item.mission_session_uuid),
                "device_uuid": str(item.device_uuid),
                "device_code_snapshot": item.device_code_snapshot,
                "device_name_snapshot": item.device_name_snapshot,
                "role": item.role,
                "joined_at": item.joined_at,
                "last_seen_at": item.last_seen_at,
                "last_pulled_mission_sequence": item.last_pulled_mission_sequence,
                "local_copy_completed_at": item.local_copy_completed_at,
                "is_connected": item.is_connected,
                "status": item.status,
            }
            for item in devices
        ],
    )


@router.get("/sessions/{mission_uuid}/devices/{device_uuid}")
def get_device(
    mission_uuid: py_uuid.UUID,
    device_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_mobile_device),
    db: Session = Depends(get_db),
):
    item = mission_service.get_device(db, mission_uuid, device_uuid)
    return success_response(
        "Mission device",
        {
            "mission_session_uuid": str(item.mission_session_uuid),
            "device_uuid": str(item.device_uuid),
            "device_code_snapshot": item.device_code_snapshot,
            "device_name_snapshot": item.device_name_snapshot,
            "role": item.role,
            "joined_at": item.joined_at,
            "last_seen_at": item.last_seen_at,
            "last_pulled_mission_sequence": item.last_pulled_mission_sequence,
            "local_copy_completed_at": item.local_copy_completed_at,
            "is_connected": item.is_connected,
            "status": item.status,
        },
    )


@router.post("/sessions/{mission_uuid}/devices/{device_uuid}/disconnect")
def disconnect_device(
    mission_uuid: py_uuid.UUID,
    device_uuid: py_uuid.UUID,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("local_network.disconnect_client")),
    db: Session = Depends(get_db),
):
    item = mission_service.disconnect_device(db, mission_uuid, device_uuid)
    return success_response("Mission device disconnected", {"device_uuid": str(item.device_uuid), "status": item.status})


@router.post("/sessions/{mission_uuid}/devices/{device_uuid}/revoke")
def revoke_device(
    mission_uuid: py_uuid.UUID,
    device_uuid: py_uuid.UUID,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("sync.disconnect_device")),
    db: Session = Depends(get_db),
):
    item = mission_service.revoke_device(db, mission_uuid, device_uuid)
    return success_response("Mission device revoked", {"device_uuid": str(item.device_uuid), "status": item.status})


@router.post("/sessions/{mission_uuid}/finalize")
def finalize_session(
    mission_uuid: py_uuid.UUID,
    __=Depends(require_installation_capability("run_mission_server")),
    current_user: User = Depends(require_permission("sync.start")),
    db: Session = Depends(get_db),
):
    manifest = mission_service.finalize_session(db, mission_uuid, current_user)
    return success_response("Mission finalized", manifest.model_dump())


@mission_sync_router.get("/pull")
def mission_pull(
    mission_uuid: py_uuid.UUID,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("perform_mission_copy")),
    db: Session = Depends(get_db),
):
    return success_response("Mission changes", mission_service.mission_pull(db, mission_uuid, after_sequence, limit))


@mission_sync_router.get("/status")
def mission_copy_status(
    mission_uuid: py_uuid.UUID,
    mission_server_uuid: py_uuid.UUID | None = Query(default=None),
    mission_server_url: str | None = Query(default=None),
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("perform_mission_copy")),
    db: Session = Depends(get_db),
):
    state = mission_copy_service.get_state(
        db,
        mission_uuid=mission_uuid,
        mission_server_uuid=mission_server_uuid,
        mission_server_url=mission_server_url,
    )
    if state is None:
        return success_response("Mission copy status", None)
    return success_response(
        "Mission copy status",
        {
            "mission_uuid": str(state.mission_session_uuid),
            "mission_server_uuid": str(state.remote_server_uuid),
            "mission_server_url": state.remote_server_url,
            "last_pulled_mission_sequence": state.last_pulled_sequence,
            "final_mission_sequence": state.final_mission_sequence,
            "copy_status": state.copy_status,
            "copy_started_at": state.copy_started_at,
            "copy_completed_at": state.copy_completed_at,
            "last_error_code": state.last_error_code,
            "last_error_message": state.last_error_message,
            "retry_count": state.retry_count,
            "is_sync_running": state.is_sync_running,
            "current_run_uuid": str(state.current_run_uuid) if state.current_run_uuid else None,
            "last_successful_sync_at": state.last_successful_sync_at,
            "last_failed_sync_at": state.last_failed_sync_at,
        },
    )


@mission_sync_router.post("/apply")
def mission_copy_apply(
    payload: MissionCopyApplyRequest,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("perform_mission_copy")),
    db: Session = Depends(get_db),
):
    state = mission_copy_service.apply_batch(
        db,
        mission_uuid=py_uuid.UUID(payload.mission_uuid),
        mission_server_uuid=py_uuid.UUID(payload.mission_server_uuid),
        mission_server_url=payload.mission_server_url,
        changes=payload.changes,
        next_sequence=payload.next_sequence,
        final_sequence=payload.final_sequence,
        current_run_uuid=py_uuid.UUID(payload.current_run_uuid) if payload.current_run_uuid else None,
    )
    return success_response(
        "Mission changes applied locally",
        {
            "mission_uuid": str(state.mission_session_uuid),
            "mission_server_uuid": str(state.remote_server_uuid),
            "mission_server_url": state.remote_server_url,
            "last_pulled_mission_sequence": state.last_pulled_sequence,
            "final_mission_sequence": state.final_mission_sequence,
            "copy_status": state.copy_status,
            "copy_started_at": state.copy_started_at,
            "copy_completed_at": state.copy_completed_at,
            "last_error_code": state.last_error_code,
            "last_error_message": state.last_error_message,
            "retry_count": state.retry_count,
            "is_sync_running": state.is_sync_running,
            "current_run_uuid": str(state.current_run_uuid) if state.current_run_uuid else None,
            "last_successful_sync_at": state.last_successful_sync_at,
            "last_failed_sync_at": state.last_failed_sync_at,
        },
    )


@mission_sync_router.get("/runs/{run_uuid}")
def mission_copy_run(
    run_uuid: py_uuid.UUID,
    _: User = Depends(get_current_user),
    __=Depends(require_installation_capability("perform_mission_copy")),
    db: Session = Depends(get_db),
):
    state = db.scalar(select(DeviceSyncState).where(DeviceSyncState.current_run_uuid == run_uuid))
    if state is None:
        return success_response("Mission copy run", None)
    return success_response(
        "Mission copy run",
        {
            "mission_uuid": str(state.mission_session_uuid),
            "mission_server_uuid": str(state.remote_server_uuid),
            "mission_server_url": state.remote_server_url,
            "last_pulled_mission_sequence": state.last_pulled_sequence,
            "final_mission_sequence": state.final_mission_sequence,
            "copy_status": state.copy_status,
            "copy_started_at": state.copy_started_at,
            "copy_completed_at": state.copy_completed_at,
            "last_error_code": state.last_error_code,
            "last_error_message": state.last_error_message,
            "retry_count": state.retry_count,
            "is_sync_running": state.is_sync_running,
            "current_run_uuid": str(state.current_run_uuid) if state.current_run_uuid else None,
            "last_successful_sync_at": state.last_successful_sync_at,
            "last_failed_sync_at": state.last_failed_sync_at,
        },
    )


@runtime_router.post("/switch-to-standalone")
def switch_to_standalone(
    payload: RuntimeSwitchRequest,
    current_user: User = Depends(get_current_user),
    __=Depends(require_mobile_device),
    db: Session = Depends(get_db),
):
    runtime = mission_service.switch_to_standalone(
        db,
        current_user,
        force=payload.force and "sync.force" in set(permission_service.get_effective_permission_codes(current_user)),
        reason=payload.reason,
    )
    return success_response("Runtime switched to standalone", {"runtime_mode": runtime.runtime_mode})


@runtime_router.get("/status")
def get_runtime_status(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Runtime status", mission_service.runtime_status(db))


@runtime_router.put("/connection-mode")
def update_connection_mode(
    payload: ConnectionModeUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # This explicit setup operation remains available to an administrator even
    # when SERVER_PC blocks normal settings administration.
    if "settings.update" not in set(permission_service.get_effective_permission_codes(current_user)):
        from app.exceptions import ForbiddenException

        raise ForbiddenException("Insufficient permissions")
    runtime, previous_connection = connection_mode_service.current(db)
    _, connection = connection_mode_service.configure(
        db,
        mode=ConnectionMode(payload.connection_mode),
        server_url=payload.server_url,
        verified=payload.connection_verified,
    )
    create_audit_log(
        db,
        user_id=current_user.id,
        actor_user_id=current_user.id,
        action="runtime.connection_mode.updated",
        entity_type="runtime_config",
        entity_id=runtime.id,
        ip_address=request.client.host if request.client else None,
        old_values=previous_connection.as_dict(),
        new_values=connection.as_dict(),
        user_agent=request.headers.get("user-agent"),
    )
    return success_response("Connection mode updated", connection.as_dict())
