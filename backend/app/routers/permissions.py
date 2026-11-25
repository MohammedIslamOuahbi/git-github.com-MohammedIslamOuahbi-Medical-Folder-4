from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.core.enums import ConnectionMode
from app.models.user import User
from app.services.permission_service import permission_service
from app.utils.responses import success_response

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("")
def list_permissions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission_service.require_any_permission(current_user, "roles.view", "users.view_permissions")
    return success_response("Permissions retrieved", permission_service.list_permissions(db))


@router.get("/effective")
def explain_effective_permissions(
    connection_mode: ConnectionMode = Query(ConnectionMode.SERVER),
    role_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_any_permission(current_user, "roles.view", "users.view_permissions")
    if user_id is not None:
        permission_service.require_permission(current_user, "users.view_permissions")
    return success_response(
        "Effective permissions retrieved",
        permission_service.explain_effective_permissions(
            db,
            actor=current_user,
            connection_mode=connection_mode,
            role_id=role_id,
            user_id=user_id,
        ),
    )
