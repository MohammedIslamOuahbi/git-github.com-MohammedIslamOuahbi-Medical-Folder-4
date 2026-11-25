from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, status
import uuid
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.pagination import PaginationParams
from app.services.company_service import CompanyService
from app.utils.responses import success_response

router = APIRouter(prefix="/companies", tags=["Companies"])
service = CompanyService()


@router.get("")
def list_companies(params: PaginationParams = Depends(get_pagination_params), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Companies retrieved", service.list(db, params).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, request: Request, operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.create(db, payload, current_user, operation_uuid)
    create_audit_log(db, current_user.id, "create", "company", item.id, request.client.host if request.client else None)
    return success_response("Company created", CompanyRead.model_validate(item).model_dump())


@router.get("/{company_id}")
def get_company(company_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Company retrieved", CompanyRead.model_validate(service.get(db, company_id)).model_dump())


@router.put("/{company_id}")
def update_company(company_id: int, payload: CompanyUpdate, request: Request, operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, company_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, company_id, payload, current_user, operation_uuid)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "company",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Company updated", CompanyRead.model_validate(item).model_dump())


@router.delete("/{company_id}")
def delete_company(company_id: int, payload: PasswordDeleteRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.delete(db, company_id, current_user, payload.password)
    create_audit_log(db, current_user.id, "delete", "company", item.id, request.client.host if request.client else None)
    return success_response("Company deleted", CompanyRead.model_validate(item).model_dump())
