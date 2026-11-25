from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditLog
from app.models.assistant_campaign import AssistantCampaign
from app.models.branch import Branch
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.company import Company
from app.models.drilling_site import DrillingSite
from app.models.doctor_campaign import DoctorCampaign
from app.models.import_job import ImportJob
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.models.worker import Worker
from app.models.worker_test import WorkerTest


class DashboardService:
    def _resolve_audit_entity_name(self, db: Session, item: AuditLog, campaigns_by_id: dict[int, str]) -> str | None:
        details = item.details_json or {}
        if item.entity_type == "campaign":
            return campaigns_by_id.get(item.entity_id)
        if item.entity_type == "company" and item.entity_id:
            company = db.scalar(select(Company).where(Company.id == item.entity_id))
            return company.name if company else None
        if item.entity_type == "branch" and item.entity_id:
            branch = db.scalar(select(Branch).where(Branch.id == item.entity_id))
            return branch.name if branch else None
        if item.entity_type == "drilling_site" and item.entity_id:
            drilling_site = db.scalar(select(DrillingSite).where(DrillingSite.id == item.entity_id))
            return drilling_site.name if drilling_site else None
        if item.entity_type == "import_job" and item.entity_id:
            import_job = db.scalar(select(ImportJob).where(ImportJob.id == item.entity_id))
            if import_job:
                return import_job.original_file_name or import_job.file_name
            return None
        if item.entity_type == "worker" and item.entity_id:
            worker = db.scalar(select(Worker).where(Worker.id == item.entity_id))
            if worker:
                return f"{worker.first_name} {worker.last_name}".strip()
            return None
        if item.entity_type == "user" and item.entity_id:
            user = db.scalar(select(User).where(User.id == item.entity_id))
            if user:
                return f"{user.first_name} {user.last_name}".strip()
            return None
        if item.entity_type == "campaign_doctor":
            if details.get("doctor_name") or details.get("doctor_names"):
                return details.get("doctor_name") or ", ".join(details.get("doctor_names", [])) or None
            if item.entity_id:
                campaign = db.scalar(
                    select(MedicalCampaign)
                    .where(MedicalCampaign.id == item.entity_id, MedicalCampaign.deleted_at.is_(None))
                    .options(selectinload(MedicalCampaign.doctor_assignments).selectinload(DoctorCampaign.doctor))
                )
                if campaign:
                    names = [
                        f"{assignment.doctor.first_name} {assignment.doctor.last_name}".strip()
                        for assignment in campaign.doctor_assignments
                        if assignment.doctor
                    ]
                    if names:
                        return ", ".join(names)
            return None
        if item.entity_type == "campaign_assistant":
            if details.get("assistant_name") or details.get("assistant_names"):
                return details.get("assistant_name") or ", ".join(details.get("assistant_names", [])) or None
            if item.entity_id:
                campaign = db.scalar(
                    select(MedicalCampaign)
                    .where(MedicalCampaign.id == item.entity_id, MedicalCampaign.deleted_at.is_(None))
                    .options(selectinload(MedicalCampaign.assistant_assignments).selectinload(AssistantCampaign.assistant))
                )
                if campaign:
                    names = [
                        f"{assignment.assistant.first_name} {assignment.assistant.last_name}".strip()
                        for assignment in campaign.assistant_assignments
                        if assignment.assistant
                    ]
                    if names:
                        return ", ".join(names)
            return None
        if item.entity_type == "campaign_worker":
            if details.get("worker_name") or details.get("worker_names"):
                return details.get("worker_name") or ", ".join(details.get("worker_names", [])) or None
            if item.entity_id:
                worker = db.scalar(select(Worker).where(Worker.id == item.entity_id))
                if worker:
                    return f"{worker.first_name} {worker.last_name}".strip()
            return None
        if item.entity_type == "campaign_test":
            if details.get("test_name") or details.get("test_names"):
                return details.get("test_name") or ", ".join(details.get("test_names", [])) or None
            if item.entity_id:
                test = db.scalar(select(MedicalTest).where(MedicalTest.id == item.entity_id))
                if test:
                    return test.name
            return None
        return None

    def _recent_campaigns(self, db: Session):
        return [
            {
                "id": item.id,
                "company_id": item.company_id,
                "branch_id": item.branch_id,
                "title": item.title,
                "doctor_name": next(
                    (
                        f"{assignment.doctor.first_name} {assignment.doctor.last_name}".strip()
                        for assignment in item.doctor_assignments
                        if assignment.doctor
                    ),
                    None,
                ),
                "company_name": item.company.name if item.company else None,
                "branch_name": item.branch.name if item.branch else None,
                "status": item.status,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "doctors_count": len(item.doctor_assignments),
                "worker_count": len(item.campaign_workers),
                "tests_count": len(item.campaign_tests),
                "assistants_count": len(item.assistant_assignments),
                "doctor_names": [
                    f"{assignment.doctor.first_name} {assignment.doctor.last_name}".strip()
                    for assignment in item.doctor_assignments
                    if assignment.doctor
                ],
                "worker_names": [
                    f"{campaign_worker.worker.first_name} {campaign_worker.worker.last_name}".strip()
                    for campaign_worker in item.campaign_workers
                    if campaign_worker.worker
                ],
                "test_names": [
                    campaign_test.test.name
                    for campaign_test in item.campaign_tests
                    if campaign_test.test
                ],
                "assistant_names": [
                    f"{assignment.assistant.first_name} {assignment.assistant.last_name}".strip()
                    for assignment in item.assistant_assignments
                    if assignment.assistant
                ],
            }
            for item in db.scalars(
                select(MedicalCampaign)
                .where(MedicalCampaign.deleted_at.is_(None))
                .options(
                    selectinload(MedicalCampaign.company),
                    selectinload(MedicalCampaign.branch),
                    selectinload(MedicalCampaign.campaign_workers).selectinload(CampaignWorker.worker),
                    selectinload(MedicalCampaign.campaign_tests).selectinload(CampaignTest.test),
                    selectinload(MedicalCampaign.doctor_assignments).selectinload(DoctorCampaign.doctor),
                    selectinload(MedicalCampaign.assistant_assignments).selectinload(AssistantCampaign.assistant),
                )
                .order_by(MedicalCampaign.id.desc())
                .limit(5)
            ).all()
        ]

    def _recent_imports(self, db: Session):
        return [
            {
                "id": item.id,
                "file_name": item.file_name,
                "status": item.status,
                "total_rows": item.total_rows,
                "created_at": item.created_at,
            }
            for item in db.scalars(select(ImportJob).order_by(ImportJob.id.desc()).limit(5)).all()
        ]

    def _recent_audit_logs(self, db: Session):
        campaigns_by_id = {
            item.id: item.title
            for item in db.scalars(
                select(MedicalCampaign)
                .where(MedicalCampaign.deleted_at.is_(None))
            ).all()
        }
        return [
            {
                "id": item.id,
                "action": item.action,
                "actor_name": (
                    f"{item.user.first_name} {item.user.last_name}".strip()
                    if item.user
                    else None
                ),
                "actor_email": item.user.email if item.user else None,
                "actor_role": item.user.role if item.user else None,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "entity_name": self._resolve_audit_entity_name(db, item, campaigns_by_id),
                "ip_address": item.ip_address,
                "details_summary": self._stringify_details(item.details_json),
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(AuditLog)
                .options(selectinload(AuditLog.user))
                .order_by(AuditLog.id.desc())
            ).all()
        ]

    def _stringify_details(self, details: dict | None) -> str | None:
        if not details:
            return None
        parts: list[str] = []
        for key, value in sorted(details.items(), key=lambda item: item[0]):
            if value in (None, "", [], {}):
                continue
            label = key.replace("_", " ").strip().title()
            if isinstance(value, dict) and "from" in value and "to" in value:
                from_value = value.get("from")
                to_value = value.get("to")
                parts.append(f"{label}: {from_value} -> {to_value}")
                continue
            parts.append(f"{label}: {value}")
        return " | ".join(parts) if parts else None

    def get_admin_dashboard(self, db: Session) -> dict:
        return {
            "total_users": db.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0,
            "total_doctors": db.scalar(select(func.count(User.id)).where(User.role == "doctor", User.deleted_at.is_(None))) or 0,
            "total_assistants": db.scalar(select(func.count(User.id)).where(User.role == "assistant", User.deleted_at.is_(None))) or 0,
            "total_companies": db.scalar(select(func.count()).select_from(Company).where(Company.deleted_at.is_(None))) or 0,
            "total_branches": db.scalar(select(func.count()).select_from(Branch).where(Branch.deleted_at.is_(None))) or 0,
            "total_drilling_sites": db.scalar(select(func.count()).select_from(DrillingSite).where(DrillingSite.deleted_at.is_(None))) or 0,
            "total_workers": db.scalar(select(func.count(Worker.id)).where(Worker.deleted_at.is_(None))) or 0,
            "total_campaigns": db.scalar(select(func.count(MedicalCampaign.id)).where(MedicalCampaign.deleted_at.is_(None))) or 0,
            "active_campaigns": db.scalar(select(func.count(MedicalCampaign.id)).where(MedicalCampaign.status == "active", MedicalCampaign.deleted_at.is_(None))) or 0,
            "completed_campaigns": db.scalar(select(func.count(MedicalCampaign.id)).where(MedicalCampaign.status == "completed", MedicalCampaign.deleted_at.is_(None))) or 0,
            "total_medical_tests": db.scalar(select(func.count(MedicalTest.id))) or 0,
            "total_worker_tests": db.scalar(select(func.count(WorkerTest.id)).where(WorkerTest.deleted_at.is_(None))) or 0,
            "abnormal_results": db.scalar(select(func.count(WorkerTest.id)).where(WorkerTest.is_normal.is_(False), WorkerTest.deleted_at.is_(None))) or 0,
            "pending_imports": db.scalar(select(func.count(ImportJob.id)).where(ImportJob.status.in_(["uploaded", "mapped", "validated"]))) or 0,
            "recent_campaigns": self._recent_campaigns(db),
            "recent_imports": self._recent_imports(db),
            "recent_audit_logs": self._recent_audit_logs(db),
        }

    def get_doctor_dashboard(self, db: Session, user_id: int | None = None) -> dict:
        del user_id
        return {
            "assigned_campaigns": db.scalar(select(func.count()).select_from(MedicalCampaign).where(MedicalCampaign.status.in_(["draft", "active"]))) or 0,
            "active_campaigns": db.scalar(select(func.count()).select_from(MedicalCampaign).where(MedicalCampaign.status == "active")) or 0,
            "pending_worker_tests": db.scalar(select(func.count()).select_from(WorkerTest).where(WorkerTest.status == "pending", WorkerTest.deleted_at.is_(None))) or 0,
            "completed_worker_tests": db.scalar(select(func.count()).select_from(WorkerTest).where(WorkerTest.status == "completed", WorkerTest.deleted_at.is_(None))) or 0,
            "abnormal_results": db.scalar(select(func.count()).select_from(WorkerTest).where(WorkerTest.is_normal.is_(False), WorkerTest.deleted_at.is_(None))) or 0,
            "workers_reviewed_today": db.scalar(select(func.count()).select_from(WorkerTest).where(WorkerTest.status == "reviewed")) or 0,
            "recent_worker_tests": [
                {
                    "id": item.id,
                    "worker_id": item.worker_id,
                    "test_id": item.test_id,
                    "status": item.status,
                    "is_normal": item.is_normal,
                    "completed_at": item.completed_at,
                }
                for item in db.scalars(select(WorkerTest).order_by(WorkerTest.id.desc()).limit(10)).all()
            ],
            "upcoming_campaigns": self._recent_campaigns(db),
        }

    def get_assistant_dashboard(self, db: Session, user_id: int | None = None) -> dict:
        del user_id
        return {
            "assigned_campaigns": db.scalar(select(func.count()).select_from(MedicalCampaign).where(MedicalCampaign.status.in_(["draft", "active"]))) or 0,
            "pending_imports": db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.status.in_(["uploaded", "mapped", "validated"]))) or 0,
            "completed_imports": db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.status == "confirmed")) or 0,
            "failed_imports": db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.status == "failed")) or 0,
            "imported_workers": db.scalar(select(func.count()).select_from(Worker).where(Worker.deleted_at.is_(None))) or 0,
            "validation_errors": sum(item.get("invalid_rows", 0) or 0 for item in [j.__dict__ for j in db.scalars(select(ImportJob)).all()]),
            "duplicate_rows": sum(item.get("duplicate_rows", 0) or 0 for item in [j.__dict__ for j in db.scalars(select(ImportJob)).all()]),
            "recent_import_jobs": self._recent_imports(db),
            "campaigns_ready_for_preparation": self._recent_campaigns(db),
        }

    def get_dashboard_for_role(self, db: Session, role: str, user_id: int | None = None) -> dict:
        if role == "admin":
            return {"role": "admin", "data": self.get_admin_dashboard(db)}
        if role == "doctor":
            return {"role": "doctor", "data": self.get_doctor_dashboard(db, user_id)}
        return {"role": "assistant", "data": self.get_assistant_dashboard(db, user_id)}
