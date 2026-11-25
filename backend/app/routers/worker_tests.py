from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.schemas.pagination import PaginationParams
from app.schemas.worker_test import WorkerTestCreate, WorkerTestRead, WorkerTestUpdate
from app.services.worker_test_service import WorkerTestService
from app.utils.responses import success_response

router = APIRouter(prefix="/worker-tests", tags=["Worker Tests"])
service = WorkerTestService()


@router.get("")
def list_worker_tests(params: PaginationParams = Depends(get_pagination_params), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker tests retrieved", service.list(db, params).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_worker_test(payload: WorkerTestCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.create(db, payload)
    create_audit_log(db, current_user.id, "create", "worker_test", item.id, request.client.host if request.client else None)
    return success_response("Worker test created", WorkerTestRead.model_validate(item).model_dump())


@router.get("/{worker_test_id}")
def get_worker_test(worker_test_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker test retrieved", WorkerTestRead.model_validate(service.get(db, worker_test_id)).model_dump())


@router.put("/{worker_test_id}")
def update_worker_test(worker_test_id: int, payload: WorkerTestUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, worker_test_id)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, worker_test_id, payload)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "worker_test",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Worker test updated", WorkerTestRead.model_validate(item).model_dump())
