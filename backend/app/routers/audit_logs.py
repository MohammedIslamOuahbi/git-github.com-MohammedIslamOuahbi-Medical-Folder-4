from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.pagination import PaginationParams
from app.services.audit_service import AuditService
from app.services.permission_service import permission_service
from app.utils.responses import success_response

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])
service = AuditService()


@router.get("")
def list_audit_logs(
    params: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    permission_service.require_permission(current_user, "audit_logs.view")
    return success_response("Audit logs retrieved", service.list(db, params).model_dump())


@router.get("/{audit_log_id}")
def get_audit_log(audit_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission_service.require_permission(current_user, "audit_logs.view")
    return success_response("Audit log retrieved", service.get(db, audit_log_id))
