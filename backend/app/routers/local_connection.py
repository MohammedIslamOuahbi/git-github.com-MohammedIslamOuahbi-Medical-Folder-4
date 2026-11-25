from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.permissions import require_permission
from app.models.user import User
from app.schemas.sync_connection import ClientConnectRequest, ClientDisconnectRequest
from app.services.local_connection_service import LocalConnectionService
from app.utils.responses import success_response

router = APIRouter(prefix="/local", tags=["Local Connection"])
service = LocalConnectionService()


@router.get("/status")
def get_status(_: User = Depends(require_permission("local_network.view_status")), db: Session = Depends(get_db)):
    return success_response("Local status retrieved", service.get_status(db, _).model_dump())


@router.post("/server/start")
def start_server(current_user: User = Depends(require_permission("local_network.start_server")), db: Session = Depends(get_db)):
    return success_response("Local server started", service.start_server(db, current_user).model_dump())


@router.post("/server/stop")
def stop_server(current_user: User = Depends(require_permission("local_network.stop_server")), db: Session = Depends(get_db)):
    return success_response("Local server stopped", service.stop_server(db, current_user).model_dump())


@router.get("/server/info")
def server_info(_: User = Depends(require_permission("local_network.view_status")), db: Session = Depends(get_db)):
    return success_response("Local server info retrieved", service.server_info(db, _).model_dump())


@router.get("/server/clients")
def server_clients(current_user: User = Depends(require_permission("local_network.manage_clients")), db: Session = Depends(get_db)):
    return success_response("Connected clients retrieved", [item.model_dump() for item in service.list_clients(db, current_user)])


@router.post("/client/connect")
def client_connect(
    payload: ClientConnectRequest,
    current_user: User = Depends(require_permission("local_network.manage_clients")),
    db: Session = Depends(get_db),
):
    return success_response("Client connected", service.connect_client(db, current_user, payload).model_dump())


@router.post("/client/disconnect")
def client_disconnect(
    payload: ClientDisconnectRequest,
    current_user: User = Depends(require_permission("local_network.disconnect_client")),
    db: Session = Depends(get_db),
):
    return success_response("Client disconnected", service.disconnect_client(db, current_user, payload).model_dump())


@router.get("/ping")
def ping(current_user: User = Depends(require_permission("local_network.view")), db: Session = Depends(get_db)):
    return success_response("Ping ok", service.ping(db, current_user))
