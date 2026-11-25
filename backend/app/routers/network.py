from __future__ import annotations

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, get_optional_current_user
from app.dependencies.database import get_db
from app.dependencies.permissions import require_permission
from app.models.user import User
from app.schemas.network import (
    MissionServerStartRequest,
    MissionServerStopRequest,
    NetworkConnectRequest,
    NetworkHeartbeatRequest,
    NetworkStatusResponse,
)
from app.services.network_service import network_hub, network_service
from app.utils.responses import success_response

router = APIRouter(prefix="/network", tags=["Network"])


@router.get("/status", response_model=NetworkStatusResponse)
def get_status(request: Request, current_user: User = Depends(require_permission("local_network.view_status")), db: Session = Depends(get_db)):
    ip_address = request.client.host if request.client else "0.0.0.0"
    device_name = f"{current_user.first_name} {current_user.last_name}".strip()
    return network_service.get_status(db, user=current_user, device_name=device_name, ip_address=ip_address)


@router.get("/discovery")
def discover_servers(_: User = Depends(require_permission("local_network.view")), db: Session = Depends(get_db)):
    return success_response("Discovered servers retrieved", [item.model_dump() for item in network_service.discover_servers(db)])


@router.post("/mission/start")
async def start_mission_server(
    payload: MissionServerStartRequest,
    request: Request,
    current_user: User = Depends(require_permission("local_network.start_server")),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else "0.0.0.0"
    result = network_service.start_mission_server(db, current_user, payload, ip_address)
    await network_hub.broadcast("server_started", result.model_dump())
    return success_response("Mission server started", result.model_dump())


@router.post("/mission/stop")
async def stop_mission_server(
    payload: MissionServerStopRequest,
    request: Request,
    current_user: User = Depends(require_permission("local_network.stop_server")),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else "0.0.0.0"
    result = network_service.stop_mission_server(db, current_user, ip_address, reason=payload.reason)
    await network_hub.broadcast("server_stopped", result.model_dump())
    return success_response("Mission server stopped", result.model_dump())


@router.post("/connect")
async def connect_client(
    payload: NetworkConnectRequest,
    request: Request,
    current_user: User = Depends(require_permission("local_network.manage_clients")),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else "0.0.0.0"
    result = network_service.connect_client(db, current_user, payload, ip_address)
    await network_hub.broadcast("user_connected", result.model_dump())
    return success_response("Client connected", result.model_dump())


@router.post("/heartbeat")
async def heartbeat(
    payload: NetworkHeartbeatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request.client else "0.0.0.0"
    if current_user is None:
        return success_response(
            "Heartbeat ignored",
            {
                "ignored": True,
                "reason": "authentication_required",
                "device_name": payload.device_name,
                "ip_address": ip_address,
            },
        )
    result = network_service.heartbeat(db, current_user, payload, ip_address)
    await network_hub.broadcast("heartbeat", result.model_dump())
    return success_response("Heartbeat recorded", result.model_dump())


@router.get("/devices")
def list_devices(_: User = Depends(require_permission("local_network.manage_clients")), db: Session = Depends(get_db)):
    return success_response("Network devices retrieved", [item.model_dump() for item in network_service.list_devices(db)])


@router.get("/logs")
def list_logs(_: User = Depends(require_permission("sync.view_logs")), db: Session = Depends(get_db)):
    return success_response("Network logs retrieved", [item.model_dump() for item in network_service.list_logs(db)])


@router.websocket("/ws")
async def network_ws(websocket: WebSocket):
    await network_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        network_hub.disconnect(websocket)
    except Exception:
        network_hub.disconnect(websocket)
