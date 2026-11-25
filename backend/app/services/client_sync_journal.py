from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

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
from app.models.orientation_certificate import OrientationCertificate
from app.models.permission import Permission
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.user import User
from app.models.user_permission import UserPermission
from app.models.worker import Worker
from app.models.worker_test import WorkerTest
from app.models.workspace import Workspace
from app.models.client_sync_change import ClientSyncChange

SYNC_MODEL_ENTITIES: dict[type, str] = {
    User: "users",
    Permission: "permissions",
    UserPermission: "user_permissions",
    Company: "companies",
    Branch: "branches",
    DrillingSite: "drilling_sites",
    MedicalTest: "medical_tests",
    MedicalCampaign: "medical_campaigns",
    CampaignWorker: "campaign_workers",
    CampaignTest: "campaign_tests",
    DoctorCampaign: "doctor_campaigns",
    AssistantCampaign: "assistant_campaigns",
    Worker: "workers",
    MedicalVisit: "medical_visits",
    WorkerTest: "worker_tests",
    Prescription: "prescriptions",
    PrescriptionItem: "prescription_items",
    OrientationCertificate: "orientation_certificates",
    AptitudeCertificate: "aptitude_certificates",
    Workspace: "workspaces",
    ImportJob: "import_jobs",
    ImportRow: "import_rows",
}

_REGISTERED = False


def _entity_for(instance: object) -> str | None:
    for model, entity in SYNC_MODEL_ENTITIES.items():
        if isinstance(instance, model):
            return entity
    return None


def _primary_key(instance: object) -> str | None:
    entity_uuid = getattr(instance, "uuid", None)
    if entity_uuid:
        return str(entity_uuid)
    identity = inspect(instance).identity
    if identity:
        return ":".join(str(part) for part in identity)
    value = getattr(instance, "id", None)
    return str(value) if value is not None else None


def _operation_for_dirty(instance: object) -> str:
    state = inspect(instance)
    deleted_attr = state.attrs.deleted_at if "deleted_at" in state.attrs else None
    if deleted_attr is not None and deleted_attr.history.has_changes() and getattr(instance, "deleted_at", None):
        return "DELETE"
    return "UPSERT"


def register_client_sync_journal() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    @event.listens_for(Session, "after_flush")
    def _record_client_sync_changes(session: Session, _flush_context) -> None:
        if session.info.get("skip_client_sync_journal"):
            return
        pending: dict[tuple[str, str], str] = {}

        for instance in session.new:
            entity = _entity_for(instance)
            entity_id = _primary_key(instance)
            if entity and entity_id:
                pending[(entity, entity_id)] = "UPSERT"

        for instance in session.dirty:
            entity = _entity_for(instance)
            entity_id = _primary_key(instance)
            if entity and entity_id and session.is_modified(instance, include_collections=False):
                pending[(entity, entity_id)] = _operation_for_dirty(instance)

        for instance in session.deleted:
            entity = _entity_for(instance)
            entity_id = _primary_key(instance)
            if entity and entity_id:
                pending[(entity, entity_id)] = "DELETE"

        if pending:
            now = datetime.now(timezone.utc)
            session.connection().execute(
                ClientSyncChange.__table__.insert(),
                [
                    {
                        "entity_type": entity,
                        "entity_id": entity_id,
                        "operation": operation,
                        "changed_at": now,
                    }
                    for (entity, entity_id), operation in pending.items()
                ],
            )

    _REGISTERED = True
