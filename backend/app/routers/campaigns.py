from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, status
import uuid
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import build_update_details, create_audit_log
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.pagination import get_pagination_params
from app.models.user import User
from app.models.local_revision import LocalWriteOperation
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_visit import MedicalVisit
from app.schemas.campaign_test import CampaignTestCreate, CampaignTestResponse
from app.schemas.campaign_worker import CampaignWorkersAssignRequest
from app.schemas.medical_campaign import (
    CampaignAssistantsAssignRequest,
    CampaignDoctorsAssignRequest,
    MedicalCampaignCreate,
    MedicalCampaignDeleteRequest,
    MedicalCampaignRead,
    MedicalCampaignUpdate,
)
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserRead
from app.schemas.worker import WorkerRead
from app.services.campaign_service import CampaignService
from app.utils.responses import success_response

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
service = CampaignService()

def _prepare_local_operation(db: Session, current_user: User, operation_uuid: uuid.UUID, campaign_id: int, payload: object) -> None:
    campaign = db.get(MedicalCampaign, campaign_id)
    if campaign is None:
        return
    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    existing = db.get(LocalWriteOperation, operation_uuid)
    if existing is not None:
        if existing.request_hash != request_hash or existing.entity_type != "campaign_tests" or existing.entity_uuid != campaign.uuid:
            from app.exceptions import BadRequestException
            raise BadRequestException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
    else:
        db.add(LocalWriteOperation(operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
            request_hash=request_hash, entity_type="campaign_tests", entity_uuid=campaign.uuid,
            result_payload={}, created_at=datetime.now(timezone.utc)))
        db.info["local_operation_uuid"] = operation_uuid
        db.info["stage3_write_contract"] = True
        db.flush()


def _normalize_medical_file_status(raw_value) -> str | None:
    normalized = str(raw_value or "").strip().lower()
    if normalized in {"confirmed", "validated", "validé", "valide"}:
        return "confirmed"
    if normalized in {"draft", "brouillon"}:
        return "draft"
    return None


def serialize_campaign_test(item) -> dict:
    return CampaignTestResponse.model_validate(
        {
            **item.__dict__,
            "campaign_test_id": item.id,
            "name": item.test.name if item.test else None,
            "description": item.test.description if item.test else None,
            "type": item.test.category if item.test and item.test.category else item.test.section if item.test else None,
            "test": item.test,
        }
    ).model_dump()


@router.get("")
def list_campaigns(params: PaginationParams = Depends(get_pagination_params), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Campaigns retrieved", service.list(db, params, current_user).model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_campaign(payload: MedicalCampaignCreate, request: Request, operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.create(db, payload, current_user=current_user, created_by=current_user.id, operation_uuid=operation_uuid)
    create_audit_log(db, current_user.id, "create", "campaign", item.id, request.client.host if request.client else None)
    return success_response("Campaign created", MedicalCampaignRead.model_validate(item).model_dump())


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Campaign retrieved", MedicalCampaignRead.model_validate(service.get(db, campaign_id, current_user)).model_dump())


@router.put("/{campaign_id}")
def update_campaign(campaign_id: int, payload: MedicalCampaignUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = service.get(db, campaign_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    details = build_update_details(before, changes)
    item = service.update(db, campaign_id, payload, current_user)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "campaign",
        item.id,
        request.client.host if request.client else None,
        details=details,
    )
    return success_response("Campaign updated", MedicalCampaignRead.model_validate(item).model_dump())


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    payload: MedicalCampaignDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = service.delete(db, campaign_id, current_user, payload.password)
    create_audit_log(
        db,
        current_user.id,
        "delete",
        "campaign",
        item.id,
        request.client.host if request.client else None,
        details={"confirmed_with_password": True},
    )
    return success_response("Campaign deleted", MedicalCampaignRead.model_validate(item).model_dump())


@router.get("/{campaign_id}/workers")
def get_campaign_workers(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = [item for item in service.get_workers(db, campaign_id, current_user) if item.worker]
    worker_ids = [item.worker.id for item in items if item.worker]

    latest_visits_by_worker_id: dict[int, MedicalVisit] = {}
    if worker_ids:
        visits = db.scalars(
            select(MedicalVisit)
            .where(MedicalVisit.worker_id.in_(worker_ids), MedicalVisit.deleted_at.is_(None))
            .order_by(MedicalVisit.worker_id.asc(), MedicalVisit.visit_date.desc(), MedicalVisit.id.desc())
        ).all()
        for visit in visits:
            if visit.worker_id is None or visit.worker_id in latest_visits_by_worker_id:
                continue
            latest_visits_by_worker_id[visit.worker_id] = visit

    return success_response(
        "Campaign workers retrieved",
        [
            WorkerRead.model_validate(
                {
                    **item.worker.__dict__,
                    "campaign_status": item.status,
                    "medical_file_status": _normalize_medical_file_status(
                        getattr(item.worker, "medical_file_status", None)
                        or getattr(item.worker, "medicalFileStatus", None)
                        or (
                            item.worker.medical_file_data.get("confirmationStatus")
                            if isinstance(item.worker.medical_file_data, dict)
                            else None
                        )
                        or (
                            item.worker.medical_file_data.get("status")
                            if isinstance(item.worker.medical_file_data, dict)
                            else None
                        )
                        or (
                            item.worker.medical_file_data.get("validationStatus")
                            if isinstance(item.worker.medical_file_data, dict)
                            else None
                        )
                    ),
                    "latest_visit_date": (
                        latest_visits_by_worker_id[item.worker.id].visit_date
                        if item.worker.id in latest_visits_by_worker_id
                        else None
                    ),
                    "latest_visit_id": (
                        latest_visits_by_worker_id[item.worker.id].id
                        if item.worker.id in latest_visits_by_worker_id
                        else None
                    ),
                }
            ).model_dump()
            for item in items
        ],
    )


@router.post("/{campaign_id}/workers")
def add_campaign_workers(
    campaign_id: int,
    payload: CampaignWorkersAssignRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.add_workers(db, campaign_id, payload.worker_ids, current_user, added_by=current_user.id)
    worker_names = [
        f"{item.worker.first_name} {item.worker.last_name}".strip()
        for item in items
        if item.worker and item.worker_id in payload.worker_ids
    ]
    create_audit_log(
        db,
        current_user.id,
        "assign",
        "campaign_worker",
        campaign_id,
        request.client.host if request.client else None,
        details={"worker_names": worker_names},
    )
    return success_response(
        "Workers assigned to campaign",
        [
            WorkerRead.model_validate(
                {
                    **item.worker.__dict__,
                    "campaign_status": item.status,
                }
            ).model_dump()
            for item in items
            if item.worker
        ],
    )


@router.delete("/{campaign_id}/workers/{worker_id}")
def remove_campaign_worker(campaign_id: int, worker_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    worker_name = next(
        (
            f"{item.worker.first_name} {item.worker.last_name}".strip()
            for item in service.get_workers(db, campaign_id, current_user)
            if item.worker_id == worker_id and item.worker
        ),
        None,
    )
    service.remove_worker(db, campaign_id, worker_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "remove",
        "campaign_worker",
        campaign_id,
        request.client.host if request.client else None,
        details={"worker_name": worker_name},
    )
    return success_response("Worker removed from campaign", {"worker_id": worker_id})


@router.get("/{campaign_id}/tests")
def get_campaign_tests(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(
        "Campaign tests retrieved",
        [
            serialize_campaign_test(item)
            for item in service.get_tests(db, campaign_id, current_user)
            if item.test
        ],
    )


@router.post("/{campaign_id}/tests")
def add_campaign_tests(
    campaign_id: int,
    payload: list[CampaignTestCreate],
    request: Request,
    operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_payload = [item.model_dump() for item in payload]
    _prepare_local_operation(db, current_user, operation_uuid, campaign_id, normalized_payload)
    items = service.add_tests(db, campaign_id, normalized_payload, current_user)
    test_names = [
        item.test.name
        for item in items
        if item.test and item.test_id in {entry["test_id"] for entry in normalized_payload}
    ]
    create_audit_log(
        db,
        current_user.id,
        "assign",
        "campaign_test",
        campaign_id,
        request.client.host if request.client else None,
        details={"test_names": test_names},
    )
    return success_response(
        "Tests assigned to campaign",
        [
            serialize_campaign_test(item)
            for item in items
            if item.test
        ],
    )


@router.put("/{campaign_id}/tests")
def replace_campaign_tests(
    campaign_id: int,
    payload: list[CampaignTestCreate],
    request: Request,
    operation_uuid: uuid.UUID = Header(alias="X-Operation-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_payload = [item.model_dump() for item in payload]
    _prepare_local_operation(db, current_user, operation_uuid, campaign_id, normalized_payload)
    items = service.replace_tests(db, campaign_id, normalized_payload, current_user)
    create_audit_log(
        db,
        current_user.id,
        "update",
        "campaign_test",
        campaign_id,
        request.client.host if request.client else None,
        details={
            "test_ids": [entry["test_id"] for entry in normalized_payload],
            "required_test_ids": [
                entry["test_id"] for entry in normalized_payload if entry.get("required")
            ],
        },
    )
    return success_response(
        "Campaign tests updated",
        [serialize_campaign_test(item) for item in items if item.test],
    )


@router.delete("/{campaign_id}/tests/{test_id}")
def remove_campaign_test(campaign_id: int, test_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    test_name = next(
        (
            item.test.name
            for item in service.get_tests(db, campaign_id, current_user)
            if item.test_id == test_id and item.test
        ),
        None,
    )
    service.remove_test(db, campaign_id, test_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "remove",
        "campaign_test",
        campaign_id,
        request.client.host if request.client else None,
        details={"test_name": test_name},
    )
    return success_response("Test removed from campaign", {"test_id": test_id})


@router.get("/{campaign_id}/doctors")
def get_campaign_doctors(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(
        "Campaign doctors retrieved",
        [
            UserRead.model_validate(item.doctor).model_dump()
            for item in service.get_doctors(db, campaign_id, current_user)
            if item.doctor
        ],
    )


@router.post("/{campaign_id}/doctors")
def add_campaign_doctors(
    campaign_id: int,
    payload: CampaignDoctorsAssignRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.add_doctors(db, campaign_id, payload.doctor_ids, current_user)
    doctor_names = [
        f"{item.doctor.first_name} {item.doctor.last_name}".strip()
        for item in items
        if item.doctor and item.doctor_id in payload.doctor_ids
    ]
    create_audit_log(
        db,
        current_user.id,
        "assign",
        "campaign_doctor",
        campaign_id,
        request.client.host if request.client else None,
        details={"doctor_names": doctor_names},
    )
    return success_response(
        "Doctors assigned to campaign",
        [UserRead.model_validate(item.doctor).model_dump() for item in items if item.doctor],
    )


@router.delete("/{campaign_id}/doctors/{doctor_id}")
def remove_campaign_doctor(campaign_id: int, doctor_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor_name = next(
        (
            f"{item.doctor.first_name} {item.doctor.last_name}".strip()
            for item in service.get_doctors(db, campaign_id, current_user)
            if item.doctor_id == doctor_id and item.doctor
        ),
        None,
    )
    service.remove_doctor(db, campaign_id, doctor_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "remove",
        "campaign_doctor",
        campaign_id,
        request.client.host if request.client else None,
        details={"doctor_name": doctor_name},
    )
    return success_response("Doctor removed from campaign", {"doctor_id": doctor_id})


@router.get("/{campaign_id}/assistants")
def get_campaign_assistants(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(
        "Campaign assistants retrieved",
        [
            UserRead.model_validate(item.assistant).model_dump()
            for item in service.get_assistants(db, campaign_id, current_user)
            if item.assistant
        ],
    )


@router.post("/{campaign_id}/assistants")
def add_campaign_assistants(
    campaign_id: int,
    payload: CampaignAssistantsAssignRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.add_assistants(db, campaign_id, payload.assistant_ids, current_user)
    assistant_names = [
        f"{item.assistant.first_name} {item.assistant.last_name}".strip()
        for item in items
        if item.assistant and item.assistant_id in payload.assistant_ids
    ]
    create_audit_log(
        db,
        current_user.id,
        "assign",
        "campaign_assistant",
        campaign_id,
        request.client.host if request.client else None,
        details={"assistant_names": assistant_names},
    )
    return success_response(
        "Assistants assigned to campaign",
        [UserRead.model_validate(item.assistant).model_dump() for item in items if item.assistant],
    )


@router.delete("/{campaign_id}/assistants/{assistant_id}")
def remove_campaign_assistant(campaign_id: int, assistant_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assistant_name = next(
        (
            f"{item.assistant.first_name} {item.assistant.last_name}".strip()
            for item in service.get_assistants(db, campaign_id, current_user)
            if item.assistant_id == assistant_id and item.assistant
        ),
        None,
    )
    service.remove_assistant(db, campaign_id, assistant_id, current_user)
    create_audit_log(
        db,
        current_user.id,
        "remove",
        "campaign_assistant",
        campaign_id,
        request.client.host if request.client else None,
        details={"assistant_name": assistant_name},
    )
    return success_response("Assistant removed from campaign", {"assistant_id": assistant_id})
