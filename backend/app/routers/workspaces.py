from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.permissions import require_permission
from app.models.user import User
from app.schemas.workspace import WorkspaceAccessRequest, WorkspaceCreate, WorkspaceSessionRead, WorkspaceUpdate
from app.services.workspace_service import WorkspaceService
from app.utils.responses import success_response

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])
service = WorkspaceService()


@router.get("")
def list_workspaces(
    _: User = Depends(require_permission("workspaces:view")),
    db: Session = Depends(get_db),
):
    return success_response("Workspaces retrieved", [item.model_dump() for item in service.list(db)])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    _: User = Depends(require_permission("workspaces:manage")),
    db: Session = Depends(get_db),
):
    return success_response("Workspace created", service.create(db, payload).model_dump())


@router.get("/by-campaign/{campaignId}")
def get_workspace_by_campaign(
    campaignId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = service.get_by_campaign_id(db, campaignId, current_user)
    service.ensure_access(workspace, current_user)
    return success_response("Workspace retrieved", service.get_workspace_read_by_campaign_id(db, campaignId, current_user).model_dump())


@router.put("/by-campaign/{campaignId}")
def update_workspace_by_campaign(
    campaignId: int,
    payload: WorkspaceUpdate,
    _: User = Depends(require_permission("workspaces:manage")),
    db: Session = Depends(get_db),
):
    return success_response("Workspace updated", service.update(db, campaignId, payload).model_dump())


@router.post("/by-campaign/{campaignId}/access")
def access_workspace(
    campaignId: int,
    payload: WorkspaceAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = WorkspaceSessionRead(workspace=service.access(db, campaignId, current_user, payload.access_code))
    return success_response("Workspace access granted", session.model_dump())
