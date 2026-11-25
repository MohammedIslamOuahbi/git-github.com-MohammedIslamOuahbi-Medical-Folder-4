from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.medicine import MedicineStatusUpdate
from app.services.medicine_service import MedicineService
from app.utils.responses import success_response

router = APIRouter(prefix="/medicines", tags=["Medicines"])
service = MedicineService()


@router.get("")
def list_medicines(
    active_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medicines retrieved",
        service.list(db, active_only=active_only, limit=limit, offset=offset).model_dump(),
    )


@router.get("/search")
def search_medicines(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    active_only: bool = Query(default=True),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medicine search retrieved",
        service.search(db, q=q, limit=limit, active_only=active_only).model_dump(),
    )


@router.get("/{medicine_id}")
def get_medicine(
    medicine_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response("Medicine retrieved", service.get(db, medicine_id).model_dump())


@router.patch("/{medicine_id}/status")
def update_medicine_status(
    medicine_id: int,
    payload: MedicineStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        "Medicine status updated",
        service.update_status(db, medicine_id, is_active=payload.is_active, current_user=current_user).model_dump(),
    )
