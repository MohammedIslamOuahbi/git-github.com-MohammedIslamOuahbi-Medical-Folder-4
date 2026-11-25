from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.aptitude_certificate import AptitudeCertificate
from app.models.assistant_campaign import AssistantCampaign
from app.models.branch import Branch
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.company import Company
from app.models.doctor_campaign import DoctorCampaign
from app.models.drilling_site import DrillingSite
from app.models.import_job import ImportJob
from app.models.import_row import ImportRow
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.medical_visit import MedicalVisit
from app.models.orientation_certificate import CertificateCounter, OrientationCertificate
from app.models.permission import Permission
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.user import User
from app.models.user_permission import UserPermission
from app.models.worker import Worker
from app.models.worker_test import WorkerTest
from app.models.workspace import Workspace


class SyncTableCategory(str, Enum):
    SYNCABLE_BUSINESS_ENTITY = "SYNCABLE_BUSINESS_ENTITY"
    SYNCABLE_RELATION = "SYNCABLE_RELATION"
    MISSION_INFRASTRUCTURE = "MISSION_INFRASTRUCTURE"
    CENTRAL_INFRASTRUCTURE = "CENTRAL_INFRASTRUCTURE"
    LOCAL_ONLY = "LOCAL_ONLY"
    SYSTEM_TABLE = "SYSTEM_TABLE"


@dataclass(frozen=True)
class SyncEntityConfig:
    entity_type: str
    model: type
    priority: int
    parent_dependencies: tuple[str, ...]
    supports_soft_delete: bool
    conflict_policy: str
    serializer_name: str
    applier_name: str


SYNC_ENTITY_REGISTRY: dict[str, SyncEntityConfig] = {
    "permissions": SyncEntityConfig("permissions", Permission, 10, (), False, "reference", "serialize_permission", "apply_permission"),
    "users": SyncEntityConfig("users", User, 20, (), True, "user", "serialize_user", "apply_user"),
    "user_permissions": SyncEntityConfig("user_permissions", UserPermission, 30, ("users", "permissions"), False, "relation", "serialize_user_permission", "apply_user_permission"),
    "companies": SyncEntityConfig("companies", Company, 40, (), True, "company", "serialize_company", "apply_company"),
    "branches": SyncEntityConfig("branches", Branch, 50, ("companies",), True, "branch", "serialize_branch", "apply_branch"),
    "drilling_sites": SyncEntityConfig("drilling_sites", DrillingSite, 60, ("companies", "branches"), True, "site", "serialize_drilling_site", "apply_drilling_site"),
    "medical_tests": SyncEntityConfig("medical_tests", MedicalTest, 65, (), True, "test_definition", "serialize_medical_test", "apply_medical_test"),
    "medical_campaigns": SyncEntityConfig("medical_campaigns", MedicalCampaign, 70, ("companies", "branches", "drilling_sites"), True, "campaign", "serialize_medical_campaign", "apply_medical_campaign"),
    "workspaces": SyncEntityConfig("workspaces", Workspace, 75, ("medical_campaigns", "companies", "branches", "drilling_sites"), False, "workspace", "serialize_workspace", "apply_workspace"),
    "workers": SyncEntityConfig("workers", Worker, 80, ("companies", "branches", "drilling_sites"), True, "worker", "serialize_worker", "apply_worker"),
    "campaign_workers": SyncEntityConfig("campaign_workers", CampaignWorker, 85, ("medical_campaigns", "workers"), False, "relation", "serialize_campaign_worker", "apply_campaign_worker"),
    "campaign_tests": SyncEntityConfig("campaign_tests", CampaignTest, 86, ("medical_campaigns", "medical_tests"), False, "relation", "serialize_campaign_test", "apply_campaign_test"),
    "doctor_campaigns": SyncEntityConfig("doctor_campaigns", DoctorCampaign, 87, ("medical_campaigns", "users"), False, "relation", "serialize_doctor_campaign", "apply_doctor_campaign"),
    "assistant_campaigns": SyncEntityConfig("assistant_campaigns", AssistantCampaign, 88, ("medical_campaigns", "users"), False, "relation", "serialize_assistant_campaign", "apply_assistant_campaign"),
    "medical_visits": SyncEntityConfig("medical_visits", MedicalVisit, 90, ("workers", "medical_campaigns", "users"), True, "visit", "serialize_medical_visit", "apply_medical_visit"),
    "worker_tests": SyncEntityConfig("worker_tests", WorkerTest, 95, ("workers", "medical_campaigns", "medical_tests", "users"), True, "worker_test", "serialize_worker_test", "apply_worker_test"),
    "prescriptions": SyncEntityConfig("prescriptions", Prescription, 100, ("workers", "medical_campaigns", "users"), True, "prescription", "serialize_prescription", "apply_prescription"),
    "prescription_items": SyncEntityConfig("prescription_items", PrescriptionItem, 105, ("prescriptions",), False, "prescription_item", "serialize_prescription_item", "apply_prescription_item"),
    "orientation_certificates": SyncEntityConfig("orientation_certificates", OrientationCertificate, 110, ("workers", "medical_campaigns", "medical_visits", "users"), True, "orientation_certificate", "serialize_orientation_certificate", "apply_orientation_certificate"),
    "aptitude_certificates": SyncEntityConfig("aptitude_certificates", AptitudeCertificate, 111, ("workers", "medical_campaigns", "medical_visits", "users"), True, "aptitude_certificate", "serialize_aptitude_certificate", "apply_aptitude_certificate"),
}


TABLE_CLASSIFICATION: dict[str, SyncTableCategory] = {
    "users": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "permissions": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "user_permissions": SyncTableCategory.SYNCABLE_RELATION,
    "companies": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "branches": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "drilling_sites": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "medical_tests": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "medical_campaigns": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "workspaces": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "workers": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "campaign_workers": SyncTableCategory.SYNCABLE_RELATION,
    "campaign_tests": SyncTableCategory.SYNCABLE_RELATION,
    "doctor_campaigns": SyncTableCategory.SYNCABLE_RELATION,
    "assistant_campaigns": SyncTableCategory.SYNCABLE_RELATION,
    "medical_visits": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "worker_tests": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "prescriptions": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "prescription_items": SyncTableCategory.SYNCABLE_RELATION,
    "orientation_certificates": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "aptitude_certificates": SyncTableCategory.SYNCABLE_BUSINESS_ENTITY,
    "sync_devices": SyncTableCategory.CENTRAL_INFRASTRUCTURE,
    "central_server_state": SyncTableCategory.CENTRAL_INFRASTRUCTURE,
    "sync_conflicts": SyncTableCategory.CENTRAL_INFRASTRUCTURE,
    "sync_runs": SyncTableCategory.CENTRAL_INFRASTRUCTURE,
    "central_bootstraps": SyncTableCategory.CENTRAL_INFRASTRUCTURE,
    "runtime_configs": SyncTableCategory.LOCAL_ONLY,
    "mission_sessions": SyncTableCategory.MISSION_INFRASTRUCTURE,
    "mission_session_devices": SyncTableCategory.MISSION_INFRASTRUCTURE,
    "sync_changes": SyncTableCategory.MISSION_INFRASTRUCTURE,
    "device_sync_states": SyncTableCategory.LOCAL_ONLY,
    "client_sync_changes": SyncTableCategory.LOCAL_ONLY,
    "client_local_sync_state": SyncTableCategory.LOCAL_ONLY,
    "client_local_sync_runs": SyncTableCategory.LOCAL_ONLY,
    "mission_servers": SyncTableCategory.LOCAL_ONLY,
    "network_devices": SyncTableCategory.LOCAL_ONLY,
    "network_logs": SyncTableCategory.LOCAL_ONLY,
    "application_initialization": SyncTableCategory.LOCAL_ONLY,
    "import_jobs": SyncTableCategory.LOCAL_ONLY,
    "import_rows": SyncTableCategory.LOCAL_ONLY,
    "medicine_imports": SyncTableCategory.LOCAL_ONLY,
    "medicine_import_errors": SyncTableCategory.LOCAL_ONLY,
    "medicines": SyncTableCategory.LOCAL_ONLY,
    "audit_logs": SyncTableCategory.LOCAL_ONLY,
    "certificate_counters": SyncTableCategory.LOCAL_ONLY,
    "alembic_version": SyncTableCategory.SYSTEM_TABLE,
}


EXCLUDED_TABLES: dict[str, str] = {
    "audit_logs": "Local operational trace; not authoritative business data.",
    "application_initialization": "Machine-local bootstrap state.",
    "certificate_counters": "Legacy local numbering helper; not globally stable.",
    "client_sync_changes": "Legacy one-way sync journal retained for compatibility.",
    "client_local_sync_state": "Legacy local sync cursor state.",
    "client_local_sync_runs": "Legacy local sync run history.",
    "mission_servers": "Legacy LAN discovery state, superseded by runtime and mission session models.",
    "network_devices": "Ephemeral connection tracking, tied to current LAN presence.",
    "network_logs": "Ephemeral local network diagnostics.",
    "import_jobs": "Operational import staging and history, not yet safe for cross-device replay.",
    "import_rows": "Temporary import staging rows with local matching details.",
    "medicine_imports": "Local catalogue import workflow state.",
    "medicine_import_errors": "Local catalogue import diagnostics.",
    "medicines": "Local reference catalogue until UUID-backed governance is added.",
}
