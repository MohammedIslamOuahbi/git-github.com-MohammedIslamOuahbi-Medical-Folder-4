from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.medical_campaign import MedicalCampaign
from app.models.worker import Worker
from app.models.worker_test import WorkerTest
from app.schemas.report import ReportFilters


class ReportService:
    def campaign_summary(self, db: Session, filters: ReportFilters) -> dict:
        query = select(
            MedicalCampaign.id,
            MedicalCampaign.company_id,
            MedicalCampaign.branch_id,
            MedicalCampaign.title,
            MedicalCampaign.status,
            MedicalCampaign.start_date,
            MedicalCampaign.end_date,
        )
        if filters.company_id:
            query = query.where(MedicalCampaign.company_id == filters.company_id)
        if filters.branch_id:
            query = query.where(MedicalCampaign.branch_id == filters.branch_id)
        if filters.campaign_id:
            query = query.where(MedicalCampaign.id == filters.campaign_id)
        return {"items": [dict(row._mapping) for row in db.execute(query).all()]}

    def company_workers(self, db: Session, filters: ReportFilters) -> dict:
        query = (
            select(Company.id, Company.name, func.count(Worker.id).label("workers"))
            .join(Worker, Worker.company_id == Company.id, isouter=True)
            .group_by(Company.id, Company.name)
        )
        if filters.company_id:
            query = query.where(Company.id == filters.company_id)
        if filters.branch_id:
            query = query.join(MedicalCampaign, MedicalCampaign.company_id == Company.id).where(MedicalCampaign.branch_id == filters.branch_id)
        if filters.campaign_id:
            campaign_company_id = db.scalar(
                select(MedicalCampaign.company_id).where(MedicalCampaign.id == filters.campaign_id)
            )
            if campaign_company_id:
                query = query.where(Company.id == campaign_company_id)
        return {"items": [dict(row._mapping) for row in db.execute(query).all()]}

    def abnormal_results(self, db: Session, filters: ReportFilters) -> dict:
        query = select(WorkerTest.id, WorkerTest.worker_id, WorkerTest.test_id, WorkerTest.result).where(
            WorkerTest.is_normal.is_(False), WorkerTest.deleted_at.is_(None)
        )
        if filters.campaign_id:
            query = query.where(WorkerTest.campaign_id == filters.campaign_id)
        return {"items": [dict(row._mapping) for row in db.execute(query).all()]}

    def worker_medical_history(self, db: Session, filters: ReportFilters) -> dict:
        query = (
            select(
                Worker.id,
                Worker.first_name,
                Worker.last_name,
                func.count(WorkerTest.id).label("tests_count"),
                func.sum(case((WorkerTest.is_normal.is_(False), 1), else_=0)).label("abnormal_count"),
            )
            .join(WorkerTest, WorkerTest.worker_id == Worker.id, isouter=True)
            .group_by(Worker.id, Worker.first_name, Worker.last_name)
        )
        if filters.campaign_id:
            query = query.where(WorkerTest.campaign_id == filters.campaign_id)
        if filters.worker_id:
            query = query.where(Worker.id == filters.worker_id)
        return {"items": [dict(row._mapping) for row in db.execute(query).all()]}
