from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.permission import RolePermissionUpdateRequest
from app.services.permission_service import permission_service
from app.utils.responses import success_response

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("")
def list_roles(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission_service.require_any_permission(current_user, "roles.view", "users.view_permissions")
    return success_response("Roles retrieved", permission_service.list_roles(db))


@router.get("/{role_id}/permissions")
def get_role_permissions(role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission_service.require_any_permission(current_user, "roles.view", "users.view_permissions")
    return success_response("Role permissions retrieved", permission_service.get_role_permissions(db, role_id))


@router.put("/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matrix = permission_service.update_role_permissions(
        db,
        role_id,
        payload,
        current_user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success_response("Role permissions updated", matrix)
