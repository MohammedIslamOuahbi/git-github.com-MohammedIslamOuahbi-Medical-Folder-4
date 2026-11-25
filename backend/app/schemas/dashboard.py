from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class DashboardCampaignItem(BaseModel):
    id: int
    company_id: int | None = None
    branch_id: int | None = None
    title: str
    doctor_name: str | None = None
    company_name: str | None = None
    branch_name: str | None = None
    status: str
    start_date: date
    end_date: date
    doctors_count: int = 0
    worker_count: int = 0
    tests_count: int = 0
    assistants_count: int = 0
    doctor_names: list[str] = []
    worker_names: list[str] = []
    test_names: list[str] = []
    assistant_names: list[str] = []


class DashboardImportItem(BaseModel):
    id: int
    file_name: str
    status: str
    total_rows: int
    created_at: datetime


class DashboardAuditItem(BaseModel):
    id: int
    action: str
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    entity_type: str
    entity_id: int | None = None
    entity_name: str | None = None
    ip_address: str | None = None
    details_summary: str | None = None
    created_at: datetime


class DashboardWorkerTestItem(BaseModel):
    id: int
    worker_id: int
    test_id: int
    status: str
    is_normal: bool | None = None
    completed_at: datetime | None = None


class AdminDashboardResponse(BaseModel):
    total_users: int
    total_doctors: int
    total_assistants: int
    total_companies: int
    total_branches: int
    total_drilling_sites: int
    total_workers: int
    total_campaigns: int
    active_campaigns: int
    completed_campaigns: int
    total_medical_tests: int
    total_worker_tests: int
    abnormal_results: int
    pending_imports: int
    recent_campaigns: list[DashboardCampaignItem]
    recent_imports: list[DashboardImportItem]
    recent_audit_logs: list[DashboardAuditItem]


class DoctorDashboardResponse(BaseModel):
    assigned_campaigns: int
    active_campaigns: int
    pending_worker_tests: int
    completed_worker_tests: int
    abnormal_results: int
    workers_reviewed_today: int
    recent_worker_tests: list[DashboardWorkerTestItem]
    upcoming_campaigns: list[DashboardCampaignItem]


class AssistantDashboardResponse(BaseModel):
    assigned_campaigns: int
    pending_imports: int
    completed_imports: int
    failed_imports: int
    imported_workers: int
    validation_errors: int
    duplicate_rows: int
    recent_import_jobs: list[DashboardImportItem]
    campaigns_ready_for_preparation: list[DashboardCampaignItem]


class DashboardMeResponse(BaseModel):
    role: Literal["admin", "doctor", "assistant"]
    data: dict[str, Any]
