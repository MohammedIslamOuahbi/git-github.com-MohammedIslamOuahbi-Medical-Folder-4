from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.drilling_site import DrillingSiteCreate, DrillingSiteRead, DrillingSiteUpdate
from app.schemas.pagination import PaginationParams
from app.services.drilling_site_service import DrillingSiteService
from app.utils.responses import success_response

router = APIRouter(prefix="/drilling-sites", tags=["Drilling Sites"])
service = DrillingSiteService()


@router.get("")
def list_sites(params: PaginationParams = Depends(get_pagination_params), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Drilling sites retrieved", service.list(db, params).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_site(payload: DrillingSiteCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.create(db, payload)
    create_audit_log(db, current_user.id, "create", "drilling_site", item.id, request.client.host if request.client else None)
    return success_response("Drilling site created", DrillingSiteRead.model_validate(item).model_dump())


@router.get("/{site_id}")
def get_site(site_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Drilling site retrieved", DrillingSiteRead.model_validate(service.get(db, site_id)).model_dump())


@router.put("/{site_id}")
def update_site(site_id: int, payload: DrillingSiteUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, site_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, site_id, payload)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "drilling_site",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Drilling site updated", DrillingSiteRead.model_validate(item).model_dump())


@router.delete("/{site_id}")
def delete_site(site_id: int, payload: PasswordDeleteRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.delete(db, site_id, current_user, payload.password)
    create_audit_log(db, current_user.id, "delete", "drilling_site", item.id, request.client.host if request.client else None)
    return success_response("Drilling site deleted", DrillingSiteRead.model_validate(item).model_dump())
