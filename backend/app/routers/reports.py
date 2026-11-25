from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.report import ReportFilters
from app.services.report_service import ReportService
from app.utils.responses import success_response

router = APIRouter(prefix="/reports", tags=["Reports"])
service = ReportService()


@router.get("/campaign-summary")
def campaign_summary(filters: ReportFilters = Depends(), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Campaign summary generated", service.campaign_summary(db, filters))


@router.get("/company-workers")
def company_workers(filters: ReportFilters = Depends(), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Company workers report generated", service.company_workers(db, filters))


@router.get("/abnormal-results")
def abnormal_results(filters: ReportFilters = Depends(), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Abnormal results report generated", service.abnormal_results(db, filters))


@router.get("/worker-medical-history")
def worker_medical_history(filters: ReportFilters = Depends(), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Worker medical history report generated", service.worker_medical_history(db, filters))
