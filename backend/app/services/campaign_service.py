from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assistant_campaign import AssistantCampaign
from app.core.permissions import has_role, user_has_permission
from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.doctor_campaign import DoctorCampaign
from app.models.company import Company
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.models.local_revision import LocalWriteOperation
from app.repositories.campaign_repository import CampaignRepository
from app.schemas.medical_campaign import MedicalCampaignCreate, MedicalCampaignUpdate
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response


class CampaignService:
    def __init__(self) -> None:
        self.repository = CampaignRepository()
        self.invalid_company_contract_message = (
            "Le contrat de cette entreprise est invalide ou expiré. Impossible de créer la campagne."
        )

    def list(self, db: Session, params: PaginationParams, current_user: User):
        items, total = self.repository.list(db, params, current_user=current_user)
        return build_paginated_response(items, total, params)

    def _has_campaign_access(self, db: Session, campaign: MedicalCampaign, current_user: User) -> bool:
        if has_role(current_user, "super_admin", "admin"):
            return True
        if has_role(current_user, "doctor"):
            return any(item.doctor_id == current_user.id for item in self.repository.get_doctors(db, campaign.id))
        if has_role(current_user, "assistant"):
            return any(item.assistant_id == current_user.id for item in self.repository.get_assistants(db, campaign.id))
        if user_has_permission(current_user, "campaigns:manage"):
            return True
        return False

    def _ensure_view_access(self, db: Session, campaign: MedicalCampaign, current_user: User) -> None:
        if not self._has_campaign_access(db, campaign, current_user):
            raise ForbiddenException("You do not have access to this campaign")

    def get(self, db: Session, campaign_id: int, current_user: User | None = None) -> MedicalCampaign:
        campaign = self.repository.get(db, campaign_id)
        if not campaign:
            raise NotFoundException("Campaign not found")
        if current_user:
            self._ensure_view_access(db, campaign, current_user)
        return campaign

    def _validate_dates(self, start_date, end_date) -> None:
        if not start_date:
            raise BadRequestException("Start date is required.")
        if not end_date:
            raise BadRequestException("End date is required.")
        if end_date < start_date:
            raise BadRequestException("End date cannot be before start date.")

    def _ensure_manage_access(self, current_user: User) -> None:
        if not user_has_permission(current_user, "campaigns:manage"):
            raise ForbiddenException("You do not have permission to manage campaigns")

    def _ensure_company_contract_valid(self, db: Session, company_id: int) -> None:
        company = db.get(Company, company_id)
        if not company or company.deleted_at is not None:
            raise NotFoundException("Company not found")

        contract_start_date = company.contract_start_date
        contract_end_date = company.contract_end_date
        today = date.today()

        if not contract_start_date or not contract_end_date:
            raise BadRequestException(self.invalid_company_contract_message)
        if contract_end_date < contract_start_date:
            raise BadRequestException(self.invalid_company_contract_message)
        if today < contract_start_date or today > contract_end_date:
            raise BadRequestException(self.invalid_company_contract_message)

    def create(
        self,
        db: Session,
        payload: MedicalCampaignCreate,
        current_user: User,
        created_by: int | None = None,
        operation_uuid: uuid.UUID | None = None,
    ) -> MedicalCampaign:
        self._ensure_manage_access(current_user)
        data = payload.model_dump()
        self._validate_dates(data.get("start_date"), data.get("end_date"))
        self._ensure_company_contract_valid(db, data["company_id"])
        data["created_by"] = created_by
        campaign = MedicalCampaign(**data)
        if operation_uuid is not None:
            entity_uuid = campaign.uuid or uuid.uuid4()
            campaign.uuid = entity_uuid
            request_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
            existing = db.get(LocalWriteOperation, operation_uuid)
            if existing is not None:
                if existing.request_hash != request_hash or existing.entity_type != "medical_campaigns":
                    raise BadRequestException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
                return db.scalar(select(MedicalCampaign).where(MedicalCampaign.uuid == existing.entity_uuid)) or campaign
            db.add(LocalWriteOperation(
                operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
                request_hash=request_hash, entity_type="medical_campaigns",
                entity_uuid=entity_uuid, result_payload={}, created_at=datetime.now(timezone.utc),
            ))
            db.info["local_operation_uuid"] = operation_uuid
            db.info["stage3_write_contract"] = True
            # Make the operation reservation visible to the write-contract
            # guard before the campaign flush is attempted.
            db.flush()
        try:
            result = self.repository.create(db, campaign)
            if operation_uuid is not None:
                db.execute(
                    LocalWriteOperation.__table__.update()
                    .where(LocalWriteOperation.operation_uuid == operation_uuid)
                    .values(result_payload={"id": result.id, "uuid": str(result.uuid)})
                )
                db.commit()
            return result
        finally:
            db.info.pop("local_operation_uuid", None)
            db.info.pop("stage3_write_contract", None)

    def _ensure_edit_access(self, campaign: MedicalCampaign, current_user: User) -> None:
        self._ensure_manage_access(current_user)
        if campaign.status == "completed" and not has_role(current_user, "super_admin"):
            raise ForbiddenException("This campaign is locked. Only super admins can edit it.")

    def _ensure_worker_assignment_access(
        self,
        db: Session,
        campaign: MedicalCampaign,
        current_user: User,
    ) -> None:
        if user_has_permission(current_user, "campaigns:manage"):
            if campaign.status == "completed" and not has_role(current_user, "super_admin"):
                raise ForbiddenException("This campaign is locked. Only super admins can edit it.")
            return

        # Assigned doctors and assistants must be able to add/remove workers from the campaign
        # because the workstation medical-file flow creates the worker first, then assigns it.
        if self._has_campaign_access(db, campaign, current_user):
            return

        raise ForbiddenException("You do not have permission to assign workers to this campaign")

    def update(self, db: Session, campaign_id: int, payload: MedicalCampaignUpdate, current_user: User) -> MedicalCampaign:
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        next_status = payload.status
        if next_status == "completed" and not has_role(current_user, "super_admin"):
            raise ForbiddenException("Only super admins can lock campaigns.")
        next_start = payload.start_date or campaign.start_date
        next_end = payload.end_date or campaign.end_date
        self._validate_dates(next_start, next_end)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(campaign, key, value)
        campaign.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, campaign)

    def delete(self, db: Session, campaign_id: int, current_user: User, password: str) -> MedicalCampaign:
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        if not password:
            raise BadRequestException("Password is required to remove a campaign.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Campaign was not removed.")
        campaign.deleted_at = datetime.now(timezone.utc)
        return self.repository.update(db, campaign)

    def get_workers(self, db: Session, campaign_id: int, current_user: User):
        self.get(db, campaign_id, current_user=current_user)
        return self.repository.get_workers(db, campaign_id)

    def add_workers(self, db: Session, campaign_id: int, worker_ids: list[int], current_user: User, added_by: int | None = None):
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_worker_assignment_access(db, campaign, current_user)
        if not worker_ids:
            raise BadRequestException("No workers provided")
        existing_ids = {item.worker_id for item in self.repository.get_workers(db, campaign_id)}
        records = [
            CampaignWorker(campaign_id=campaign_id, worker_id=worker_id, added_by=added_by)
            for worker_id in worker_ids
            if worker_id not in existing_ids
        ]
        if not records:
            return self.repository.get_workers(db, campaign_id)
        db.add_all(records)
        db.commit()
        return self.repository.get_workers(db, campaign_id)

    def remove_worker(self, db: Session, campaign_id: int, worker_id: int, current_user: User) -> None:
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_worker_assignment_access(db, campaign, current_user)
        assignment = next((item for item in self.repository.get_workers(db, campaign_id) if item.worker_id == worker_id), None)
        if not assignment:
            raise NotFoundException("Campaign worker not found")
        db.delete(assignment)
        db.commit()

    def get_tests(self, db: Session, campaign_id: int, current_user: User):
        self.get(db, campaign_id, current_user=current_user)
        return self.repository.get_tests(db, campaign_id)

    def _validate_campaign_test_payload(
        self,
        db: Session,
        payload: list[dict[str, bool | int]],
        *,
        allow_empty: bool = False,
    ) -> dict[int, MedicalTest]:
        if not payload and allow_empty:
            return {}
        if not payload:
            raise BadRequestException("No tests provided")

        test_ids = [int(item["test_id"]) for item in payload]
        duplicate_ids = sorted({test_id for test_id in test_ids if test_ids.count(test_id) > 1})
        if duplicate_ids:
            raise BadRequestException("Duplicate test ids are not allowed in the same campaign payload.")

        tests = db.scalars(select(MedicalTest).where(MedicalTest.id.in_(test_ids))).all()
        tests_by_id = {item.id: item for item in tests}
        missing_ids = [test_id for test_id in test_ids if test_id not in tests_by_id]
        if missing_ids:
            raise NotFoundException(f"Medical test(s) not found: {', '.join(str(item) for item in missing_ids)}")
        inactive_ids = [test_id for test_id, test in tests_by_id.items() if not test.is_active]
        if inactive_ids:
            raise BadRequestException(
                f"Inactive medical test(s) cannot be assigned: {', '.join(str(item) for item in inactive_ids)}"
            )

        return tests_by_id

    def add_tests(
        self,
        db: Session,
        campaign_id: int,
        payload: list[dict[str, bool | int]],
        current_user: User,
    ):
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        self._validate_campaign_test_payload(db, payload)
        existing_ids = {item.test_id for item in self.repository.get_tests(db, campaign_id)}
        overlapping_ids = sorted(
            int(item["test_id"])
            for item in payload
            if int(item["test_id"]) in existing_ids
        )
        if overlapping_ids:
            raise BadRequestException(
                f"These tests are already assigned to the campaign: {', '.join(str(item) for item in overlapping_ids)}"
            )
        records = [
            CampaignTest(
                campaign_id=campaign_id,
                test_id=int(item["test_id"]),
                required=bool(item.get("required", True)),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for item in payload
        ]
        db.add_all(records)
        db.commit()
        return self.repository.get_tests(db, campaign_id)

    def replace_tests(
        self,
        db: Session,
        campaign_id: int,
        payload: list[dict[str, bool | int]],
        current_user: User,
    ):
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        self._validate_campaign_test_payload(db, payload, allow_empty=True)

        existing = self.repository.get_tests(db, campaign_id)
        existing_by_test_id = {item.test_id: item for item in existing}
        incoming_ids = {int(item["test_id"]) for item in payload}

        for assignment in existing:
            if assignment.test_id not in incoming_ids:
                db.delete(assignment)

        for item in payload:
            test_id = int(item["test_id"])
            required = bool(item.get("required", True))
            assignment = existing_by_test_id.get(test_id)
            if assignment:
                assignment.required = required
                assignment.updated_at = datetime.now(timezone.utc)
                continue
            db.add(
                CampaignTest(
                    campaign_id=campaign_id,
                    test_id=test_id,
                    required=required,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        db.commit()
        return self.repository.get_tests(db, campaign_id)

    def remove_test(self, db: Session, campaign_id: int, test_id: int, current_user: User) -> None:
        campaign = self.get(db, campaign_id)
        self._ensure_edit_access(campaign, current_user)
        assignment = next((item for item in self.repository.get_tests(db, campaign_id) if item.test_id == test_id), None)
        if not assignment:
            raise NotFoundException("Campaign test not found")
        db.delete(assignment)
        db.commit()

    def get_doctors(self, db: Session, campaign_id: int, current_user: User):
        self.get(db, campaign_id, current_user=current_user)
        return self.repository.get_doctors(db, campaign_id)

    def add_doctors(self, db: Session, campaign_id: int, doctor_ids: list[int], current_user: User):
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        if not doctor_ids:
            raise BadRequestException("No doctors provided")
        existing_ids = {item.doctor_id for item in self.repository.get_doctors(db, campaign_id)}
        records = [
            DoctorCampaign(campaign_id=campaign_id, doctor_id=doctor_id)
            for doctor_id in doctor_ids
            if doctor_id not in existing_ids
        ]
        if not records:
            return self.repository.get_doctors(db, campaign_id)
        db.add_all(records)
        db.commit()
        return self.repository.get_doctors(db, campaign_id)

    def remove_doctor(self, db: Session, campaign_id: int, doctor_id: int, current_user: User) -> None:
        campaign = self.get(db, campaign_id)
        self._ensure_edit_access(campaign, current_user)
        assignment = next((item for item in self.repository.get_doctors(db, campaign_id) if item.doctor_id == doctor_id), None)
        if not assignment:
            raise NotFoundException("Campaign doctor not found")
        db.delete(assignment)
        db.commit()

    def get_assistants(self, db: Session, campaign_id: int, current_user: User):
        self.get(db, campaign_id, current_user=current_user)
        return self.repository.get_assistants(db, campaign_id)

    def add_assistants(self, db: Session, campaign_id: int, assistant_ids: list[int], current_user: User):
        campaign = self.get(db, campaign_id, current_user=current_user)
        self._ensure_edit_access(campaign, current_user)
        if not assistant_ids:
            raise BadRequestException("No assistants provided")
        existing_ids = {item.assistant_id for item in self.repository.get_assistants(db, campaign_id)}
        records = [
            AssistantCampaign(campaign_id=campaign_id, assistant_id=assistant_id)
            for assistant_id in assistant_ids
            if assistant_id not in existing_ids
        ]
        if not records:
            return self.repository.get_assistants(db, campaign_id)
        db.add_all(records)
        db.commit()
        return self.repository.get_assistants(db, campaign_id)

    def remove_assistant(self, db: Session, campaign_id: int, assistant_id: int, current_user: User) -> None:
        campaign = self.get(db, campaign_id)
        self._ensure_edit_access(campaign, current_user)
        assignment = next((item for item in self.repository.get_assistants(db, campaign_id) if item.assistant_id == assistant_id), None)
        if not assignment:
            raise NotFoundException("Campaign assistant not found")
        db.delete(assignment)
        db.commit()
