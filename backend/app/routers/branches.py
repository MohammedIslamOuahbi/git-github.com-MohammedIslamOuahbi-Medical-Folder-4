from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate
from app.schemas.pagination import PaginationParams
from app.services.branch_service import BranchService
from app.utils.responses import success_response

router = APIRouter(prefix="/branches", tags=["Branches"])
service = BranchService()


@router.get("")
def list_branches(params: PaginationParams = Depends(get_pagination_params), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Branches retrieved", service.list(db, params).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_branch(payload: BranchCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.create(db, payload)
    create_audit_log(db, current_user.id, "create", "branch", item.id, request.client.host if request.client else None)
    return success_response("Branch created", BranchRead.model_validate(item).model_dump())


@router.get("/{branch_id}")
def get_branch(branch_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Branch retrieved", BranchRead.model_validate(service.get(db, branch_id)).model_dump())


@router.put("/{branch_id}")
def update_branch(branch_id: int, payload: BranchUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, branch_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, branch_id, payload)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "branch",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Branch updated", BranchRead.model_validate(item).model_dump())


@router.delete("/{branch_id}")
def delete_branch(branch_id: int, payload: PasswordDeleteRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.delete(db, branch_id, current_user, payload.password)
    create_audit_log(db, current_user.id, "delete", "branch", item.id, request.client.host if request.client else None)
    return success_response("Branch deleted", BranchRead.model_validate(item).model_dump())
