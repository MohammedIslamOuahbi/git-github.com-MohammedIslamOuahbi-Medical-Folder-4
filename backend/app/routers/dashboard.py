from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.permissions import require_any_permission, require_permission
from app.models.user import User
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AssistantDashboardResponse,
    DashboardMeResponse,
    DoctorDashboardResponse,
)
from app.services.dashboard_service import DashboardService
from app.utils.responses import success_response

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
service = DashboardService()


@router.get("/admin")
def get_admin_dashboard(_: User = Depends(require_any_permission("reports.view", "reports.statistics")), db: Session = Depends(get_db)):
    return success_response("Admin dashboard retrieved", AdminDashboardResponse(**service.get_admin_dashboard(db)).model_dump())


@router.get("/doctor")
def get_doctor_dashboard(current_user: User = Depends(require_permission("reports.view")), db: Session = Depends(get_db)):
    return success_response("Doctor dashboard retrieved", DoctorDashboardResponse(**service.get_doctor_dashboard(db, current_user.id)).model_dump())


@router.get("/assistant")
def get_assistant_dashboard(current_user: User = Depends(require_permission("reports.view")), db: Session = Depends(get_db)):
    return success_response("Assistant dashboard retrieved", AssistantDashboardResponse(**service.get_assistant_dashboard(db, current_user.id)).model_dump())


@router.get("/me")
def get_dashboard_for_authenticated_user(current_user: User = Depends(require_permission("reports.view")), db: Session = Depends(get_db)):
    return success_response("Role dashboard retrieved", DashboardMeResponse(**service.get_dashboard_for_role(db, current_user.role, current_user.id)).model_dump())
