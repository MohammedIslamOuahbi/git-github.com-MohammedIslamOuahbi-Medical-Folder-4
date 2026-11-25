from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.services.workspace_service import WorkspaceService

service = WorkspaceService()


def get_workspace_by_campaign_id(
    campaignId: int,
    db: Session = Depends(get_db),
) -> Workspace:
    return service.get_by_campaign_id(db, campaignId)


def require_workspace_access(
    workspace: Workspace = Depends(get_workspace_by_campaign_id),
    current_user: User = Depends(get_current_user),
) -> Workspace:
    service.ensure_access(workspace, current_user)
    return workspace
