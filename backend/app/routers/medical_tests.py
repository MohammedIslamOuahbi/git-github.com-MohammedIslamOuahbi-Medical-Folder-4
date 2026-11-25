from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.core.permissions import require_permission
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.common import PasswordDeleteRequest
from app.schemas.medical_test import MedicalTestCreate, MedicalTestRead, MedicalTestUpdate
from app.schemas.pagination import PaginationParams
from app.services.medical_test_service import MedicalTestService
from app.utils.responses import success_response

router = APIRouter(prefix="/medical-tests", tags=["Medical Tests"])
service = MedicalTestService()


@router.get("")
def list_medical_tests(
    params: PaginationParams = Depends(get_pagination_params),
    active: bool | None = Query(default=None),
    current_user: User = Depends(require_permission("medical_tests.view")),
    db: Session = Depends(get_db),
):
    _ = current_user
    return success_response(
        "Medical tests retrieved",
        service.list(db, params, active=active).model_dump(),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_medical_test(payload: MedicalTestCreate, request: Request, current_user: User = Depends(require_permission("medical_tests:manage")), db: Session = Depends(get_db)):
    item = service.create(db, payload)
    create_audit_log(db, current_user.id, "create", "medical_test", item.id, request.client.host if request.client else None)
    return success_response("Medical test created", MedicalTestRead.model_validate(item).model_dump())


@router.get("/{test_id}")
def get_medical_test(
    test_id: int,
    current_user: User = Depends(require_permission("medical_tests.view")),
    db: Session = Depends(get_db),
):
    _ = current_user
    return success_response(
        "Medical test retrieved",
        MedicalTestRead.model_validate(service.get(db, test_id)).model_dump(),
    )


@router.put("/{test_id}")
def update_medical_test(test_id: int, payload: MedicalTestUpdate, request: Request, current_user: User = Depends(require_permission("medical_tests:manage")), db: Session = Depends(get_db)):
    before = service.get(db, test_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, test_id, payload)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "medical_test",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Medical test updated", MedicalTestRead.model_validate(item).model_dump())


@router.delete("/{test_id}")
def delete_medical_test(test_id: int, payload: PasswordDeleteRequest, request: Request, current_user: User = Depends(require_permission("medical_tests:manage")), db: Session = Depends(get_db)):
    item = service.delete(db, test_id, current_user, payload.password)
    create_audit_log(db, current_user.id, "delete", "medical_test", item.id, request.client.host if request.client else None)
    return success_response("Medical test deleted", MedicalTestRead.model_validate(item).model_dump())
