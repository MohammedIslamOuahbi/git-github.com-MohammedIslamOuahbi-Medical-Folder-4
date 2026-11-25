from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from datetime import datetime, timezone ,date
from uuid import uuid4
import uuid as py_uuid

from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.dialects.postgresql import insert
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, NotFoundException, ForbiddenException
from app.models.aptitude_certificate import AptitudeCertificate
from app.models.campaign_worker import CampaignWorker
from app.models.orientation_certificate import OrientationCertificate
from app.models.medical_visit import MedicalVisit
from app.models.local_revision import LocalWriteOperation, LocalEditAttempt
from app.models.user import User
from app.models.worker import Worker
from app.models.medical_campaign import MedicalCampaign
from app.schemas.medical_visit import (
    MedicalVisitCreate,
    MedicalVisitDuplicateRequest,
    MedicalVisitRead,
    MedicalVisitStatusUpdate,
    MedicalVisitUpdate,
    MedicalVisitValidateRequest,
)
from app.services.signature_authorization import (
    ensure_signature_payload_authorized,
    normalize_validator_signature_dict,
)
from app.services.user_signature_service import UserSignatureService
from app.services.protected_visit_write import apply_visit_update
from app.exceptions import ConflictException
from app.models.sync_change import SyncChange
from app.services.authorization_evidence_service import capture_authorization_execution


class MedicalVisitService:
    editable_for_assistant = {"draft", "basic_info_completed", "tests_in_progress", "needs_correction"}
    doctor_editable = editable_for_assistant | {"ready_for_doctor", "validated", "synced"}
    structured_form_data_version = 1
    allowed_visit_form_keys = {
        "internalVisit",
        "clinicalExam",
        "complementaryExams",
        "medicalDecision",
        "dynamicMedicalTests",
        "profilTaGlycemie",
        "aptitudeCertificate",
        "orientationCertificates",
        "workStoppageCertificate",
        "ordonnances",
        "validation",
        "auditTrail",
    }

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
    
    def _to_date(self, value):
        if not value:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if isinstance(value, str):
            return datetime.strptime(value[:10], "%Y-%m-%d").date()

        return None

    def _parse_snapshot_datetime(self, value: object) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        normalized = str(value).strip().replace("Z", "+00:00")
        if not normalized:
            return None
        return datetime.fromisoformat(normalized)

    def _serialize(self, visit: MedicalVisit) -> MedicalVisitRead:
        return MedicalVisitRead(
            id=visit.id,
            uuid=visit.uuid,
            worker_id=visit.worker_id,
            worker_uuid=visit.worker_uuid,
            campaign_id=visit.campaign_id,
            campaign_uuid=visit.campaign_uuid,
            visit_date=visit.visit_date,
            site_name=visit.site_name,
            status=visit.status,
            form_data=self._normalize_form_data(visit, visit.form_data),
            created_by=visit.created_by,
            updated_by=visit.updated_by,
            validated_by=visit.validated_by,
            validated_at=visit.validated_at,
            doctor_notes=visit.doctor_notes,
            sync_status=visit.sync_status,
            version=visit.version,
            created_at=visit.created_at,
            updated_at=visit.updated_at,
            deleted_at=visit.deleted_at,
        )

    def _get(self, db: Session, visit_id: int) -> MedicalVisit:
        visit = db.scalar(select(MedicalVisit).where(MedicalVisit.id == visit_id, MedicalVisit.deleted_at.is_(None)))
        if not visit:
            raise NotFoundException("Medical visit not found")
        return visit

    def _validate_worker_campaign(self, db: Session, payload: MedicalVisitCreate) -> None:
        if payload.worker_id is not None and not db.scalar(select(Worker).where(Worker.id == payload.worker_id)):
            raise NotFoundException("Worker not found")
        if payload.campaign_id is not None and not db.scalar(select(MedicalCampaign).where(MedicalCampaign.id == payload.campaign_id)):
            raise NotFoundException("Campaign not found")

    def _can_edit(self, current_user: User, visit: MedicalVisit) -> bool:
        role = (current_user.role or "").strip().lower()
        if role in {"super_admin", "super admin", "admin", "doctor"}:
            return True
        if role == "assistant":
            return visit.status in self.editable_for_assistant
        return False

    def create(self, db: Session, payload: MedicalVisitCreate, current_user: User,
               operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        if not current_user.is_active:
            raise ForbiddenException("LOCAL_WRITE_ACCESS_DENIED")
        request_hash = hashlib.sha256(json.dumps(jsonable_encoder(payload.model_dump()), sort_keys=True,
                                                separators=(",", ":")).encode("utf-8")).hexdigest()
        existing_operation = db.get(LocalWriteOperation, operation_uuid)
        if existing_operation is not None:
            if (existing_operation.actor_user_uuid != current_user.uuid or existing_operation.request_hash != request_hash
                    or existing_operation.entity_type != "medical_visits"):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            db.info["local_write_replay"] = True
            replay_payload = existing_operation.result_payload or {}
            return MedicalVisitRead.model_validate(replay_payload.get("result", replay_payload))
        self._validate_worker_campaign(db, payload)
        worker = self._get_worker(db, payload.worker_id) if payload.worker_id else None
        normalized_form_data = self._normalize_incoming_form_data(
            payload.form_data or {},
            worker=worker,
            visit_date=payload.visit_date,
            site_name=payload.site_name,
            current_user=current_user,
        )
        self._ensure_signature_authorized(current_user, normalized_form_data)
        visit_uuid = uuid4()
        # Creation has no preexisting entity UUID; fingerprint the request separately.
        visit = MedicalVisit(
            uuid=visit_uuid,
            worker_id=payload.worker_id,
            worker_uuid=payload.worker_uuid,
            campaign_id=payload.campaign_id,
            campaign_uuid=payload.campaign_uuid,
            visit_date=payload.visit_date,
            site_name=payload.site_name,
            status=payload.status or "draft",
            form_data=normalized_form_data,
            created_by=current_user.id,
            updated_by=current_user.id,
            sync_status="pending_sync",
            version=1,
            deleted_at=None,
        )
        return self._commit_new_visit(db, visit, current_user, operation_uuid, request_hash)

    def _commit_new_visit(self, db: Session, visit: MedicalVisit, current_user: User,
                          operation_uuid: py_uuid.UUID, request_hash: str) -> MedicalVisitRead:
        if not current_user.is_active:
            raise ForbiddenException("LOCAL_WRITE_ACCESS_DENIED")
        if db.get(LocalEditAttempt, operation_uuid) is not None:
            raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
        try:
            reserved = db.execute(insert(LocalWriteOperation).values(
                operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
                request_hash=request_hash, entity_type="medical_visits", entity_uuid=visit.uuid,
                result_payload={}, created_at=self._now(),
            ).on_conflict_do_nothing(index_elements=[LocalWriteOperation.operation_uuid])
              .returning(LocalWriteOperation.operation_uuid)).scalar_one_or_none()
            if reserved is None:
                existing = db.get(LocalWriteOperation, operation_uuid)
                if (existing is None or existing.actor_user_uuid != current_user.uuid
                        or existing.request_hash != request_hash or existing.entity_type != "medical_visits"):
                    raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
                db.info["local_write_replay"] = True
                replay_payload = existing.result_payload or {}
                return MedicalVisitRead.model_validate(replay_payload.get("result", replay_payload))
            db.info["local_write_replay"] = False
            db.info["local_operation_uuid"] = operation_uuid
            db.info["stage3_write_contract"] = True
            db.add(visit)
            db.flush()
            change = db.scalar(select(SyncChange).where(
                SyncChange.operation_uuid == operation_uuid,
                SyncChange.entity_type == "medical_visits",
                SyncChange.entity_uuid == visit.uuid,
            ))
            if change is not None:
                capture_authorization_execution(
                    db, user=current_user, operation=db.get(LocalWriteOperation, operation_uuid),
                    event=change, permission_code="medical_visits.create",
                    scope=f"clinic:{db.info.get('sync_source_clinic_uuid')}:medical_visits:create",
                    policy_version="5A-P1-20261014",
                )
            self._ensure_visit_certificates(db, visit, current_user)
            result = self._serialize(visit)
            existing_payload = db.scalar(select(LocalWriteOperation.result_payload).where(
                LocalWriteOperation.operation_uuid == operation_uuid)) or {}
            db.execute(sql_update(LocalWriteOperation).where(LocalWriteOperation.operation_uuid == operation_uuid)
                       .values(result_payload={**existing_payload, "result": jsonable_encoder(result)}))
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.info.pop("local_operation_uuid", None)
            db.info.pop("stage3_write_contract", None)

    def get(self, db: Session, visit_id: int) -> MedicalVisitRead:
        return self._serialize(self._get(db, visit_id))

    def list_by_worker(self, db: Session, worker_id: int) -> list[MedicalVisitRead]:
        visits = db.scalars(
            select(MedicalVisit)
            .where(MedicalVisit.worker_id == worker_id, MedicalVisit.deleted_at.is_(None))
            .order_by(MedicalVisit.visit_date.desc(), MedicalVisit.id.desc())
        ).all()
        return [self._serialize(item) for item in visits]

    def duplicate(
        self,
        db: Session,
        worker_id: int,
        visit_id: int,
        payload: MedicalVisitDuplicateRequest,
        current_user: User,
        operation_uuid: py_uuid.UUID,
    ) -> MedicalVisitRead:
        if not current_user.is_active:
            raise ForbiddenException("LOCAL_WRITE_ACCESS_DENIED")
        request_hash = hashlib.sha256(json.dumps(jsonable_encoder({"source_visit_id": visit_id,
            "worker_id": worker_id, "payload": payload.model_dump()}), sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        existing_operation = db.get(LocalWriteOperation, operation_uuid)
        if existing_operation is not None:
            if (existing_operation.actor_user_uuid != current_user.uuid or existing_operation.request_hash != request_hash
                    or existing_operation.entity_type != "medical_visits"):
                raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            db.info["local_write_replay"] = True
            return MedicalVisitRead.model_validate(existing_operation.result_payload)
        source = self._get(db, visit_id)
        if source.worker_id != worker_id:
            raise NotFoundException("Medical visit not found")

        copied_form_data = dict(source.form_data or {})
        normalized_copy = self._normalize_incoming_form_data(
            copied_form_data,
            worker=self._get_worker(db, worker_id),
            visit_date=date.today(),
            site_name=payload.site_name or source.site_name,
            current_user=current_user,
        )
        normalized_copy["visitData"]["validation"] = {}
        normalized_copy["visitData"]["medicalDecision"] = {}
        self._ensure_signature_authorized(current_user, normalized_copy)

        visit = MedicalVisit(
            uuid=str(uuid4()),
            worker_id=worker_id,
            worker_uuid=source.worker_uuid,
            campaign_id=payload.campaign_id or source.campaign_id,
            campaign_uuid=source.campaign_uuid,
            visit_date=date.today().isoformat(),
            site_name=payload.site_name or source.site_name,
            status="pending",
            form_data=normalized_copy,
            created_by=current_user.id,
            updated_by=current_user.id,
            validated_by=None,
            validated_at=None,
            doctor_notes=None,
            sync_status="pending_sync",
            version=1,
            deleted_at=None,
        )
        return self._commit_new_visit(db, visit, current_user, operation_uuid, request_hash)

    def build_lookup_history(self, db: Session, worker: Worker) -> dict:
        visits = self.list_by_worker(db, worker.id)
        companies = []
        branches = []
        sites = []
        campaigns = []
        visit_payloads = []

        worker_company = getattr(worker, "company", None)
        worker_branch = getattr(worker, "branch", None)
        worker_site = getattr(worker, "drilling_site", None)

        if worker_company:
            companies.append({"id": worker_company.id, "name": worker_company.name})
        if worker_branch:
            branches.append({"id": worker_branch.id, "name": worker_branch.name})
        if worker_site:
            sites.append({"id": worker_site.id, "name": worker_site.name})

        for visit in visits:
            visit_data = self._normalize_visit_view(visit.form_data or {})
            campaign_name = self._get_legacy_value(visit_data, "campaignName", "campaign_name") or ""
            company_name = self._get_legacy_value(visit_data, "companyName", "company_name") or ""
            branch_name = self._get_legacy_value(visit_data, "branchName", "branch_name") or ""
            site_name = self._get_legacy_value(visit_data, "siteName", "site_name") or visit.site_name or ""
            tests = self._extract_visit_tests(visit_data)
            decision = visit_data.get("visitData", {}).get("medicalDecision") or visit_data.get("medicalDecision") or {}
            visit_payloads.append(
                {
                    "id": visit.id,
                    "visit_date": visit.visit_date,
                    "status": visit.status,
                    "company_name": company_name or None,
                    "branch_name": branch_name or None,
                    "site_name": site_name or None,
                    "campaign_name": campaign_name or None,
                    "tests": tests,
                    "summary": self._summarize_visit(visit_data),
                    "medical_decision": decision,
                }
            )

            if campaign_name:
                campaigns.append({"id": visit.campaign_id, "name": campaign_name})
            if company_name:
                companies.append({"name": company_name})
            if branch_name:
                branches.append({"name": branch_name})
            if site_name:
                sites.append({"name": site_name})

        return {
            "companies": self._unique_items(companies),
            "branches": self._unique_items(branches),
            "sites": self._unique_items(sites),
            "campaigns": self._unique_items(campaigns),
            "visits": visit_payloads,
            "total_medical_visits": len(visit_payloads),
            "total_medical_tests": sum(len(item["tests"]) for item in visit_payloads),
        }

    @staticmethod
    def _unique_items(items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for item in items:
            key = f"{item.get('id')}-{item.get('name')}"
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _extract_visit_tests(visit_data: dict) -> list[str]:
        visit_data = visit_data.get("visitData") if isinstance(visit_data.get("visitData"), dict) else visit_data
        raw_tests = []
        if isinstance(visit_data.get("selectedTests"), list):
            raw_tests = visit_data["selectedTests"]
        elif isinstance(visit_data.get("tests"), list):
            raw_tests = visit_data["tests"]
        elif isinstance(visit_data.get("campaignTests"), list):
            raw_tests = visit_data["campaignTests"]

        tests: list[str] = []
        for item in raw_tests:
            if isinstance(item, str) and item.strip():
                tests.append(item.strip())
            elif isinstance(item, dict):
                label = item.get("label") or item.get("name") or item.get("test_name")
                if label:
                    tests.append(str(label).strip())
        return tests

    @staticmethod
    def _summarize_visit(visit_data: dict) -> dict:
        visit_data = visit_data.get("visitData") if isinstance(visit_data.get("visitData"), dict) else visit_data
        keys = ["internalVisit", "clinicalExam", "complementaryExams", "medicalDecision"]
        summary = {}
        for key in keys:
            value = visit_data.get(key)
            if isinstance(value, dict):
                summary[key] = {"fields": list(value.keys())[:6]}
        return summary

    def update(self, db: Session, visit_id: int, payload: MedicalVisitUpdate, current_user: User,
               expected_version: int, operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        visit = self._get(db, visit_id)
        if not self._can_edit(current_user, visit):
            raise ForbiddenException("You are not allowed to edit this visit")
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and current_user.role and current_user.role.strip().lower() == "assistant":
            if visit.status == "validated":
                raise ForbiddenException("Validated visit cannot be edited by assistant")
            if data["status"] not in self.editable_for_assistant:
                raise ForbiddenException("Assistant can only edit draft-like visits")
        values = {}
        for key, value in data.items():
            if key == "form_data":
                next_form_data = self._normalize_incoming_form_data(
                    value,
                    worker=visit.worker or self._get_worker(db, visit.worker_id),
                    visit_date=visit.visit_date,
                    site_name=visit.site_name,
                    current_user=current_user,
                )
                self._ensure_signature_authorized(current_user, next_form_data, visit.form_data or {})
                values["form_data"] = next_form_data
                continue
            if key in {"visit_date", "site_name", "status", "doctor_notes"}:
                values[key] = value
        return apply_visit_update(db, current_user, visit, action="update", expected_version=expected_version,
                                  operation_uuid=operation_uuid, attempted_payload=data, values=values,
                                  before_commit=lambda session, current: self._ensure_visit_certificates(session, current, current_user))

    def update_status(self, db: Session, visit_id: int, payload: MedicalVisitStatusUpdate, current_user: User,
                      expected_version: int, operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        visit = self._get(db, visit_id)
        if not self._can_edit(current_user, visit):
            raise ForbiddenException("You are not allowed to edit this visit")
        return apply_visit_update(db, current_user, visit, action="status", expected_version=expected_version,
                                  operation_uuid=operation_uuid, attempted_payload=payload.model_dump(),
                                  values={"status": payload.status},
                                  before_commit=lambda session, current: self._ensure_visit_certificates(session, current, current_user))

    def validate(self, db: Session, visit_id: int, payload: MedicalVisitValidateRequest, current_user: User,
                 expected_version: int, operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        visit = self._get(db, visit_id)
        role = (current_user.role or "").strip().lower()
        if role not in {"super_admin", "super admin", "admin", "doctor"}:
            raise ForbiddenException("Only doctor/admin can validate visits")
        form_data = self._normalize_incoming_form_data(
            visit.form_data or {},
            worker=visit.worker or self._get_worker(db, visit.worker_id),
            visit_date=visit.visit_date,
            site_name=visit.site_name,
            current_user=current_user,
        )
        return apply_visit_update(db, current_user, visit, action="validate", expected_version=expected_version,
                                  operation_uuid=operation_uuid, attempted_payload=payload.model_dump(),
                                  values={"form_data": form_data, "status": "validated",
                                          "validated_by": current_user.id, "validated_at": self._now(),
                                          "doctor_notes": payload.doctor_notes or visit.doctor_notes})

    def reopen(self, db: Session, visit_id: int, current_user: User,
               expected_version: int, operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        visit = self._get(db, visit_id)
        role = (current_user.role or "").strip().lower()
        if role not in {"super_admin", "super admin", "admin", "doctor"}:
            raise ForbiddenException("Only doctor/admin can reopen visits")
        return apply_visit_update(db, current_user, visit, action="reopen", expected_version=expected_version,
                                  operation_uuid=operation_uuid, attempted_payload={},
                                  values={"status": "needs_correction"})

    def get_test_results(self, db: Session, visit_id: int) -> dict:
        visit = self._get(db, visit_id)
        return {"visit_id": visit.id, "form_data": self._normalize_form_data(visit, visit.form_data)}

    def save_test_results(self, db: Session, visit_id: int, payload: dict, current_user: User,
                          expected_version: int, operation_uuid: py_uuid.UUID) -> MedicalVisitRead:
        visit = self._get(db, visit_id)
        if not self._can_edit(current_user, visit):
            raise ForbiddenException("You are not allowed to edit this visit")
        next_form_data = self._normalize_incoming_form_data(
            payload,
            worker=visit.worker or self._get_worker(db, visit.worker_id),
            visit_date=visit.visit_date,
            site_name=visit.site_name,
            current_user=current_user,
        )
        self._ensure_signature_authorized(current_user, next_form_data, visit.form_data or {})
        return apply_visit_update(db, current_user, visit, action="test_results", expected_version=expected_version,
                                  operation_uuid=operation_uuid, attempted_payload=payload,
                                  values={"form_data": next_form_data},
                                  before_commit=lambda session, current: self._ensure_visit_certificates(session, current, current_user))

    def _get_worker(self, db: Session, worker_id: int | None) -> Worker | None:
        if worker_id is None:
            return None
        return db.scalar(select(Worker).where(Worker.id == worker_id))

    def _ensure_signature_authorized(
        self,
        current_user: User,
        payload: dict,
        existing_payload: dict | None = None,
    ) -> None:
        ensure_signature_payload_authorized(
            user=current_user,
            payload=payload,
            existing_payload=existing_payload,
        )

    def _normalize_incoming_form_data(
        self,
        payload: dict | None,
        worker: Worker | None = None,
        visit_date: str | None = None,
        site_name: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        raw = deepcopy(payload or {})
        visit_container = raw.get("visitData") if isinstance(raw.get("visitData"), dict) else raw
        worker_snapshot = self._normalize_worker_snapshot(
            deepcopy(raw.get("workerSnapshot") or {}),
            worker,
            raw,
            visit_date,
            site_name,
        )
        visit_data = {
            "internalVisit": self._extract_internal_visit(visit_container),
            "clinicalExam": self._extract_group(visit_container, "clinicalExam"),
            "complementaryExams": self._extract_group(visit_container, "complementaryExams"),
            "medicalDecision": self._extract_group(visit_container, "medicalDecision"),
            "dynamicMedicalTests": deepcopy(visit_container.get("dynamicMedicalTests") or {}),
            "profilTaGlycemie": self._extract_group(visit_container, "profilTaGlycemie"),
            "aptitudeCertificate": self._extract_group(visit_container, "aptitudeCertificate"),
            "orientationCertificates": self._extract_orientation_collection(visit_container),
            "workStoppageCertificate": self._extract_optional_group(visit_container, "workStoppageCertificate"),
            "ordonnances": self._extract_ordonnances_collection(visit_container),
            "validation": self._extract_group(visit_container, "validation"),
            "auditTrail": deepcopy(
                visit_container.get("auditTrail")
                or raw.get("auditTrail")
                or raw.get("audit_trail")
                or []
            ),
        }
        normalized = self._normalize_visit_data(visit_data, worker_snapshot, visit_container, worker, visit_date, current_user)
        return {key: normalized.get(key) for key in self.allowed_visit_form_keys}

    def _normalize_form_data(self, visit: MedicalVisit, payload: dict | None) -> dict:
        normalized = self._normalize_incoming_form_data(
            payload,
            worker=visit.worker,
            visit_date=visit.visit_date,
            site_name=visit.site_name,
        )
        return self._add_legacy_view(normalized)

    def _normalize_visit_view(self, payload: dict | None) -> dict:
        normalized = self._normalize_incoming_form_data(payload, worker=None)
        return self._add_legacy_view(normalized)

    def _extract_group(self, raw: dict, prefix: str) -> dict:
        value = raw.get(prefix)
        if isinstance(value, dict):
            return deepcopy(value)
        return {}

    def _extract_optional_group(self, raw: dict, prefix: str) -> dict | None:
        value = raw.get(prefix)
        if isinstance(value, dict):
            return deepcopy(value)
        return None

    def _extract_orientation_collection(self, raw: dict) -> list[dict]:
        if isinstance(raw.get("orientationCertificates"), list):
            return [deepcopy(item) for item in raw.get("orientationCertificates", []) if isinstance(item, dict)]
        singular = raw.get("orientationCertificate")
        if isinstance(singular, dict):
            return [deepcopy(singular)]
        return []

    def _extract_ordonnances_collection(self, raw: dict) -> list[dict]:
        if isinstance(raw.get("ordonnances"), list):
            return [deepcopy(item) for item in raw.get("ordonnances", []) if isinstance(item, dict)]
        singular = raw.get("ordonnance")
        if isinstance(singular, dict):
            return [deepcopy(singular)]
        return []

    def _normalize_worker_snapshot(
        self,
        worker_snapshot: dict,
        worker: Worker | None,
        raw: dict,
        visit_date: str | None,
        site_name: str | None,
    ) -> dict:
        normalized = deepcopy(worker_snapshot or {})
        if worker and isinstance(worker.medical_file_data, dict):
            source = worker.medical_file_data
        else:
            source = raw

        normalized.setdefault("medicalFileNumber", self._coerce_snapshot_value(source.get("medicalFileNumber")))
        normalized.setdefault("employeeCode", self._coerce_snapshot_value(source.get("employeeCode")))
        normalized.setdefault("nationalId", self._coerce_snapshot_value(source.get("nationalId")))
        normalized.setdefault("firstName", self._coerce_snapshot_value(source.get("firstName")))
        normalized.setdefault("lastName", self._coerce_snapshot_value(source.get("lastName")))
        normalized.setdefault("sex", self._coerce_snapshot_value(source.get("sex")))
        normalized.setdefault("dateOfBirth", self._coerce_snapshot_value(source.get("dateOfBirth")))
        normalized.setdefault("birthPlace", self._coerce_snapshot_value(source.get("birthPlace")))
        normalized.setdefault("phone", self._coerce_snapshot_value(source.get("phone")))
        normalized.setdefault("addresses", self._coerce_snapshot_value(source.get("addresses")))
        normalized.setdefault("companyName", self._coerce_snapshot_value(source.get("companyName")))
        normalized.setdefault("siteName", self._coerce_snapshot_value(site_name or source.get("siteName")))
        normalized.setdefault("position", self._coerce_snapshot_value(source.get("position") or getattr(worker, "job_title", "")))
        normalized.setdefault("department", self._coerce_snapshot_value(source.get("department") or getattr(worker, "department", "")))
        normalized.setdefault("bloodGroup", self._coerce_snapshot_value(source.get("bloodGroup") or getattr(worker, "blood_group", "")))
        normalized.setdefault("rhesus", self._coerce_snapshot_value(source.get("rhesus") or getattr(worker, "gropage_rh", "")))
        normalized.setdefault("professionalHistory", deepcopy(source.get("professionalHistory") or []))
        normalized.setdefault("vaccinations", deepcopy(source.get("vaccinations") or []))
        normalized.setdefault("workAccidents", deepcopy(source.get("workAccidents") or []))
        normalized.setdefault("occupationalDiseases", deepcopy(source.get("occupationalDiseases") or []))
        normalized.setdefault("spontaneousConsultations", deepcopy(source.get("spontaneousConsultations") or []))
        normalized.setdefault("visitDate", self._coerce_snapshot_value(visit_date or source.get("visitDate")))
        return normalized

    def _normalize_visit_data(
        self,
        visit_data: dict,
        worker_snapshot: dict,
        raw: dict,
        worker: Worker | None,
        visit_date: str | None,
        current_user: User | None = None,
    ) -> dict:
        normalized = deepcopy(visit_data or {})
        internal_visit = normalized.get("internalVisit") if isinstance(normalized.get("internalVisit"), dict) else {}
        medical_decision = normalized.get("medicalDecision") if isinstance(normalized.get("medicalDecision"), dict) else {}
        validation = normalized.get("validation") if isinstance(normalized.get("validation"), dict) else {}

        orientation_certificates = normalized.get("orientationCertificates") if isinstance(normalized.get("orientationCertificates"), list) else []
        aptitude_certificate = normalized.get("aptitudeCertificate") if isinstance(normalized.get("aptitudeCertificate"), dict) else {}

        normalized["internalVisit"] = self._normalize_internal_visit(internal_visit, raw)
        normalized["clinicalExam"] = deepcopy(normalized.get("clinicalExam") or self._extract_group(raw, "clinicalExam"))
        normalized["complementaryExams"] = deepcopy(normalized.get("complementaryExams") or self._extract_group(raw, "complementaryExams"))
        normalized["medicalDecision"] = self._normalize_medical_decision(medical_decision, validation, raw)
        normalized["dynamicMedicalTests"] = deepcopy(normalized.get("dynamicMedicalTests") or raw.get("dynamicMedicalTests") or {})
        normalized["profilTaGlycemie"] = self._normalize_profil_ta_glycemie(
            normalized.get("profilTaGlycemie") or self._extract_group(raw, "profilTaGlycemie"),
            worker_snapshot,
        )
        normalized["validation"] = self._normalize_validation(validation, raw, current_user)
        normalized["orientationCertificates"] = self._normalize_orientation_certificate_snapshot(
            orientation_certificates,
            worker_snapshot,
            normalized["medicalDecision"],
            normalized["validation"],
            worker,
            raw,
            current_user,
        )
        normalized["aptitudeCertificate"] = self._build_aptitude_snapshot(
            aptitude_certificate,
            worker_snapshot,
            normalized["medicalDecision"],
            normalized["validation"],
            worker,
            raw,
            visit_date,
            current_user,
        )
        normalized["workStoppageCertificate"] = self._normalize_work_stoppage_certificate(
            normalized.get("workStoppageCertificate"),
            worker_snapshot,
            normalized["validation"],
            worker,
            current_user,
        )
        normalized["ordonnances"] = self._extract_ordonnances_collection(normalized)
        normalized["auditTrail"] = deepcopy(normalized.get("auditTrail") or raw.get("auditTrail") or [])
        return normalized

    def _normalize_profil_ta_glycemie(self, payload: object, worker_snapshot: dict) -> dict:
        source = deepcopy(payload) if isinstance(payload, dict) else {}
        rows = source.get("rows") if isinstance(source.get("rows"), list) else []
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_rows.append(
                {
                    "id": self._coerce_snapshot_value(row.get("id")) or str(uuid4()),
                    "date": self._coerce_snapshot_value(row.get("date")),
                    "rightArm": self._coerce_snapshot_value(row.get("rightArm") or row.get("tensionArterielle")),
                    "leftArm": self._coerce_snapshot_value(row.get("leftArm")),
                    "time": self._coerce_snapshot_value(row.get("time")),
                    "glycemia": self._coerce_snapshot_value(row.get("glycemia") or row.get("glycemie")),
                }
            )
        if not normalized_rows:
            normalized_rows.append(
                {
                    "id": str(uuid4()),
                    "date": "",
                    "rightArm": self._coerce_snapshot_value(source.get("tensionArterielle")),
                    "leftArm": "",
                    "time": "",
                    "glycemia": self._coerce_snapshot_value(source.get("glycemie")),
                }
            )
        return {
            "fullName": self._coerce_snapshot_value(
                source.get("fullName")
                or f"{worker_snapshot.get('firstName', '')} {worker_snapshot.get('lastName', '')}".strip()
            ),
            "rows": normalized_rows,
        }

    def _normalize_work_stoppage_certificate(
        self,
        payload: object,
        worker_snapshot: dict,
        validation: dict,
        worker: Worker | None,
        current_user: User | None,
    ) -> dict | None:
        if not isinstance(payload, dict):
            return None
        source = deepcopy(payload)
        worker_full_name = f"{worker_snapshot.get('firstName', '')} {worker_snapshot.get('lastName', '')}".strip()
        birth_date = worker_snapshot.get("dateOfBirth") or getattr(worker, "birth_date", None)
        worker_age = ""
        if birth_date:
            parsed_birth_date = self._to_date(birth_date)
            if parsed_birth_date is not None:
                today_value = date.today()
                worker_age_number = today_value.year - parsed_birth_date.year - (
                    (today_value.month, today_value.day) < (parsed_birth_date.month, parsed_birth_date.day)
                )
                worker_age = str(max(worker_age_number, 0))
        return {
            "doctorFullName": self._coerce_snapshot_value(
                source.get("doctorFullName")
                or source.get("doctorName")
                or validation.get("validatingDoctor")
                or getattr(current_user, "full_name", "")
            ),
            "workerFullName": self._coerce_snapshot_value(source.get("workerFullName") or worker_full_name),
            "workerAge": self._coerce_snapshot_value(source.get("workerAge") or worker_age),
            "position": self._coerce_snapshot_value(source.get("position") or worker_snapshot.get("position")),
            "workStopDuration": self._coerce_snapshot_value(source.get("workStopDuration") or source.get("days")),
            "workStopExtensionDuration": self._coerce_snapshot_value(source.get("workStopExtensionDuration")),
            "returnToWork": bool(source.get("returnToWork")),
            "startDate": self._coerce_snapshot_value(source.get("startDate")),
            "endDate": self._coerce_snapshot_value(source.get("endDate")),
            "issuedAt": self._coerce_snapshot_value(source.get("issuedAt")) or date.today().isoformat(),
            "status": "validated" if self._coerce_snapshot_value(source.get("status")) == "validated" else "draft",
            "includeValidatorSignature": bool(source.get("includeValidatorSignature")),
        }

    def _normalize_internal_visit(self, internal_visit: dict, raw: dict) -> dict:
        normalized = deepcopy(internal_visit or {})
        normalized.setdefault("hire", bool(raw.get("internalVisitHire")))
        normalized.setdefault("periodic", bool(raw.get("internalVisitPeriodic")))
        normalized.setdefault("date", self._coerce_snapshot_value(raw.get("internalVisitDate")))
        normalized.setdefault("doctor", self._coerce_snapshot_value(raw.get("internalVisitDoctor")))
        normalized.setdefault("weightKg", self._coerce_snapshot_value(raw.get("internalVisitWeightKg")))
        normalized.setdefault("heightCm", self._coerce_snapshot_value(raw.get("internalVisitHeightCm")))
        normalized.setdefault("ta", self._coerce_snapshot_value(raw.get("internalVisitTa")))
        normalized.setdefault("fc", self._coerce_snapshot_value(raw.get("internalVisitFc")))
        normalized.setdefault("distanceOdSc", self._coerce_snapshot_value(raw.get("internalVisitDistanceOdSc")))
        normalized.setdefault("distanceOdAc", self._coerce_snapshot_value(raw.get("internalVisitDistanceOdAc")))
        normalized.setdefault("distanceOgSc", self._coerce_snapshot_value(raw.get("internalVisitDistanceOgSc")))
        normalized.setdefault("distanceOgAc", self._coerce_snapshot_value(raw.get("internalVisitDistanceOgAc")))
        normalized.setdefault("distanceOdg", self._coerce_snapshot_value(raw.get("internalVisitDistanceOdg")))
        return normalized

    def _normalize_medical_decision(self, medical_decision: dict, validation: dict, raw: dict) -> dict:
        normalized = deepcopy(medical_decision or {})
        if validation:
            normalized.pop("validation", None)
        normalized.setdefault("orientation", deepcopy(raw.get("orientation") or normalized.get("orientation") or {}))
        normalized.setdefault("specialistResponse", deepcopy(normalized.get("specialistResponse") or {}))
        normalized.setdefault("cat", deepcopy(normalized.get("cat") or {}))
        normalized.setdefault("restrictions", deepcopy(normalized.get("restrictions") or {}))
        normalized.setdefault("recommendations", deepcopy(normalized.get("recommendations") or {}))
        normalized.setdefault("nextVisit", deepcopy(normalized.get("nextVisit") or {}))
        return normalized

    def _normalize_validation(self, validation: dict, raw: dict, current_user: User | None = None) -> dict:
        normalized = deepcopy(validation or {})
        normalized.setdefault("status", self._coerce_snapshot_value(raw.get("status")) or "confirmed")
        normalized.setdefault("validatingDoctor", self._coerce_snapshot_value(raw.get("validatingDoctor") or raw.get("internalVisitDoctor")))
        normalized.setdefault("validationDate", self._coerce_snapshot_value(raw.get("validationDate") or raw.get("updated_at") or raw.get("visitDate")))
        normalized.setdefault("electronicSignature", self._coerce_snapshot_value(raw.get("electronicSignature")))
        normalized.setdefault("isLocked", bool(raw.get("isLocked")))
        normalized_signature = normalize_validator_signature_dict(
            normalized,
            current_user=current_user,
            existing_payload=validation,
        )
        if current_user and normalized_signature.get("includeValidatorSignature"):
            UserSignatureService().require_uploaded_signature(current_user)
        return normalized_signature

    def normalize_certificate_snapshot(
        self,
        payload: object,
        current_user: User | None = None,
        existing_payload: object | None = None,
    ) -> dict:
        return normalize_validator_signature_dict(
            payload,
            current_user=current_user,
            existing_payload=existing_payload,
        )

    def _normalize_orientation_certificate_snapshot(
        self,
        payload: object,
        worker_snapshot: dict,
        medical_decision: dict,
        validation: dict,
        worker: Worker | None,
        raw: dict,
        current_user: User | None = None,
    ) -> object:
        if isinstance(payload, list):
            return [
                self._build_orientation_snapshot(item, worker_snapshot, medical_decision, validation, worker, raw)
                for item in payload
                if self._is_explicit_orientation_snapshot(item)
            ]

        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            entries = [
                self._build_orientation_snapshot(item, worker_snapshot, medical_decision, validation, worker, raw)
                for item in payload.get("entries", [])
                if self._is_explicit_orientation_snapshot(item)
            ]
            normalized_group = self.normalize_certificate_snapshot(payload, current_user=current_user, existing_payload=payload)
            normalized_group["entries"] = entries
            return normalized_group

        return self._build_orientation_snapshot(
            payload if isinstance(payload, dict) else {},
            worker_snapshot,
            medical_decision,
            validation,
            worker,
            raw,
            current_user,
        )

    def _build_orientation_snapshot(
        self,
        snapshot: dict,
        worker_snapshot: dict,
        medical_decision: dict,
        validation: dict,
        worker: Worker | None,
        raw: dict,
        current_user: User | None = None,
    ) -> dict:
        existing = self.normalize_certificate_snapshot(snapshot, existing_payload=snapshot)
        normalized = {
            "id": existing.get("id"),
            "uuid": self._coerce_snapshot_value(existing.get("uuid")),
            "orientationNumber": self._coerce_snapshot_value(
                existing.get("orientationNumber")
                or existing.get("orientation_number")
                or raw.get("orientationNumber")
                or raw.get("orientation_number")
            ),
            "orientationDate": self._coerce_snapshot_value(existing.get("orientationDate") or raw.get("orientationDate") or raw.get("orientation_date")),
            "age": self._coerce_snapshot_value(existing.get("age") or raw.get("age")),
            "patientFullName": self._coerce_snapshot_value(
                existing.get("patientFullName")
                or f"{worker_snapshot.get('firstName', '')} {worker_snapshot.get('lastName', '')}".strip()
            ),
            "prescribingDoctor": self._coerce_snapshot_value(
                existing.get("prescribingDoctor")
                or validation.get("validatingDoctor")
                or medical_decision.get("validation", {}).get("validatingDoctor")
                or raw.get("internalVisitDoctor")
            ),
            "orientationType": self._coerce_snapshot_value(existing.get("orientationType") or raw.get("orientation_type")),
            "orientationTypes": deepcopy(existing.get("orientationTypes") or raw.get("orientationTypes") or raw.get("orientation_types") or {}),
            "orientationTypeOther": self._coerce_snapshot_value(existing.get("orientationTypeOther") or raw.get("orientation_type_other")),
            "orientationDetails": self._coerce_snapshot_value(existing.get("orientationDetails") or raw.get("orientation_details")),
            "includeValidatorSignature": bool(
                existing.get("includeValidatorSignature")
                or validation.get("includeValidatorSignature")
                or raw.get("includeWorkspaceSignature")
            ),
            "status": self._coerce_snapshot_value(existing.get("status") or raw.get("status") or "draft"),
        }
        return self.normalize_certificate_snapshot(normalized, current_user=current_user, existing_payload=existing)

    def _build_aptitude_snapshot(
        self,
        snapshot: dict,
        worker_snapshot: dict,
        medical_decision: dict,
        validation: dict,
        worker: Worker | None,
        raw: dict,
        visit_date: str | None,
        current_user: User | None = None,
    ) -> dict:
        existing = self.normalize_certificate_snapshot(snapshot, existing_payload=snapshot)
        normalized = {
            "id": existing.get("id"),
            "uuid": self._coerce_snapshot_value(existing.get("uuid")),
            "certificateNumber": self._coerce_snapshot_value(existing.get("certificateNumber") or existing.get("certificate_number") or raw.get("certificateNumber")),
            "lastName": self._coerce_snapshot_value(existing.get("lastName") or worker_snapshot.get("lastName") or getattr(worker, "last_name", "")),
            "firstName": self._coerce_snapshot_value(existing.get("firstName") or worker_snapshot.get("firstName") or getattr(worker, "first_name", "")),
            "dateOfBirth": self._coerce_snapshot_value(existing.get("dateOfBirth") or worker_snapshot.get("dateOfBirth")),
            "birthPlace": self._coerce_snapshot_value(existing.get("birthPlace") or worker_snapshot.get("birthPlace")),
            "bloodGroup": self._coerce_snapshot_value(existing.get("bloodGroup") or worker_snapshot.get("bloodGroup")),
            "rhesus": self._coerce_snapshot_value(existing.get("rhesus") or worker_snapshot.get("rhesus")),
            "aptitude": self._normalize_aptitude_value(existing.get("aptitude") or medical_decision.get("aptitude")),
            "position": self._coerce_snapshot_value(existing.get("position") or worker_snapshot.get("position")),
            "aptitudeDate": self._coerce_snapshot_value(existing.get("aptitudeDate") or validation.get("validationDate") or visit_date),
            "companyName": self._coerce_snapshot_value(existing.get("companyName") or worker_snapshot.get("companyName")),
            "doctorRecommendations": self._coerce_snapshot_value(
                existing.get("doctorRecommendations")
                or medical_decision.get("recommendations", {}).get("doctorRecommendations")
            ),
            "prescribingDoctor": self._coerce_snapshot_value(
                existing.get("prescribingDoctor")
                or validation.get("validatingDoctor")
                or raw.get("internalVisitDoctor")
            ),
            "includeValidatorSignature": bool(
                existing.get("includeValidatorSignature")
                or validation.get("includeValidatorSignature")
                or raw.get("includeWorkspaceSignature")
            ),
            "status": self._coerce_snapshot_value(existing.get("status") or validation.get("status") or raw.get("status") or "draft"),
        }
        return self.normalize_certificate_snapshot(normalized, current_user=current_user, existing_payload=existing)

    def _extract_internal_visit(self, raw: dict) -> dict:
        nested = raw.get("internalVisit")
        if isinstance(nested, dict):
            return deepcopy(nested)

        return {
            "hire": raw.get("internalVisitHire"),
            "periodic": raw.get("internalVisitPeriodic"),
            "date": raw.get("internalVisitDate"),
            "doctor": raw.get("internalVisitDoctor"),
            "weightKg": raw.get("internalVisitWeightKg"),
            "heightCm": raw.get("internalVisitHeightCm"),
            "ta": raw.get("internalVisitTa"),
            "fc": raw.get("internalVisitFc"),
            "distanceOdSc": raw.get("internalVisitDistanceOdSc"),
            "distanceOdAc": raw.get("internalVisitDistanceOdAc"),
            "distanceOgSc": raw.get("internalVisitDistanceOgSc"),
            "distanceOgAc": raw.get("internalVisitDistanceOgAc"),
            "distanceOdg": raw.get("internalVisitDistanceOdg"),
        }

    def _build_worker_snapshot(
        self,
        worker: Worker | None,
        raw: dict,
        visit_date: str | None,
        site_name: str | None,
    ) -> dict:
        worker_data = raw.get("workerSnapshot") if isinstance(raw.get("workerSnapshot"), dict) else {}
        medical_file_data = worker.medical_file_data if worker and isinstance(worker.medical_file_data, dict) else {}
        return {
            "medicalFileNumber": self._coerce_snapshot_value(
                worker_data.get("medicalFileNumber")
                or raw.get("medicalFileNumber")
                or medical_file_data.get("medicalFileNumber")
                or worker_data.get("medical_file_number")
            ),
            "employeeCode": self._coerce_snapshot_value(
                worker_data.get("employeeCode")
                or raw.get("employeeCode")
                or medical_file_data.get("employeeCode")
                or (worker.employee_number if worker else raw.get("employeeCode"))
            ),
            "nationalId": self._coerce_snapshot_value(
                worker_data.get("nationalId")
                or raw.get("nationalId")
                or medical_file_data.get("nationalId")
                or (worker.national_id if worker else raw.get("nationalId"))
            ),
            "firstName": self._coerce_snapshot_value(
                worker_data.get("firstName") or raw.get("firstName") or (worker.first_name if worker else "")
            ),
            "lastName": self._coerce_snapshot_value(
                worker_data.get("lastName") or raw.get("lastName") or (worker.last_name if worker else "")
            ),
            "sex": self._coerce_snapshot_value(worker_data.get("sex") or raw.get("sex") or (worker.gender if worker else "")),
            "dateOfBirth": self._coerce_snapshot_value(
                worker_data.get("dateOfBirth")
                or raw.get("dateOfBirth")
                or (worker.birth_date.isoformat() if worker and worker.birth_date else "")
            ),
            "birthPlace": self._coerce_snapshot_value(
                worker_data.get("birthPlace")
                or raw.get("birthPlace")
                or (worker.birth_wilaya if worker else "")
            ),
            "phone": self._coerce_snapshot_value(worker_data.get("phone") or raw.get("phone") or (worker.phone if worker else "")),
            "addresses": self._coerce_snapshot_value(
                worker_data.get("addresses")
                or raw.get("addresses")
                or (worker.address if worker else "")
            ),
            "companyName": self._coerce_snapshot_value(
                worker_data.get("companyName") or raw.get("companyName") or ""
            ),
            "siteName": self._coerce_snapshot_value(worker_data.get("siteName") or raw.get("siteName") or site_name or ""),
            "professionalHistory": deepcopy(worker_data.get("professionalHistory") or raw.get("professionalHistory") or []),
            "vaccinations": deepcopy(worker_data.get("vaccinations") or raw.get("vaccinations") or []),
            "workAccidents": deepcopy(worker_data.get("workAccidents") or raw.get("workAccidents") or []),
            "occupationalDiseases": deepcopy(worker_data.get("occupationalDiseases") or raw.get("occupationalDiseases") or []),
            "spontaneousConsultations": deepcopy(worker_data.get("spontaneousConsultations") or raw.get("spontaneousConsultations") or []),
            "visitDate": self._coerce_snapshot_value(visit_date or raw.get("visitDate") or raw.get("internalVisitDate") or ""),
        }

    def _add_legacy_view(self, structured: dict) -> dict:
        view = deepcopy(structured)
        visit_data = view.get("visitData") if isinstance(view.get("visitData"), dict) else view
        if not isinstance(visit_data, dict):
            return view

        internal_visit = visit_data.get("internalVisit", {}) if isinstance(visit_data.get("internalVisit"), dict) else {}
        orientation_certificates = (
            visit_data.get("orientationCertificates")
            if isinstance(visit_data.get("orientationCertificates"), list)
            else []
        )

        aliases = {
            "internalVisit": visit_data.get("internalVisit", {}),
            "clinicalExam": visit_data.get("clinicalExam", {}),
            "complementaryExams": visit_data.get("complementaryExams", {}),
            "medicalDecision": visit_data.get("medicalDecision", {}),
            "dynamicMedicalTests": visit_data.get("dynamicMedicalTests", {}),
            "profilTaGlycemie": visit_data.get("profilTaGlycemie", {}),
            "orientationCertificates": orientation_certificates,
            "orientationCertificate": orientation_certificates[0] if orientation_certificates else visit_data.get("orientationCertificate", {}),
            "aptitudeCertificate": visit_data.get("aptitudeCertificate", {}),
            "workStoppageCertificate": visit_data.get("workStoppageCertificate"),
            "ordonnances": visit_data.get("ordonnances", []),
            "validation": visit_data.get("validation", {}),
            "auditTrail": visit_data.get("auditTrail", view.get("auditTrail", [])),
        }
        for key, value in aliases.items():
            view.setdefault(key, value)

        flat_internal_visit_aliases = {
            "internalVisitHire": internal_visit.get("hire", ""),
            "internalVisitPeriodic": internal_visit.get("periodic", ""),
            "internalVisitDate": internal_visit.get("date", ""),
            "internalVisitDoctor": internal_visit.get("doctor", ""),
            "internalVisitWeightKg": internal_visit.get("weightKg", ""),
            "internalVisitHeightCm": internal_visit.get("heightCm", ""),
            "internalVisitTa": internal_visit.get("ta", ""),
            "internalVisitFc": internal_visit.get("fc", ""),
            "internalVisitDistanceOdSc": internal_visit.get("distanceOdSc", ""),
            "internalVisitDistanceOdAc": internal_visit.get("distanceOdAc", ""),
            "internalVisitDistanceOgSc": internal_visit.get("distanceOgSc", ""),
            "internalVisitDistanceOgAc": internal_visit.get("distanceOgAc", ""),
            "internalVisitDistanceOdg": internal_visit.get("distanceOdg", ""),
        }
        for key, value in flat_internal_visit_aliases.items():
            view.setdefault(key, value)
        return view

    def _get_legacy_value(self, visit_data: dict, *keys: str) -> str:
        for key in keys:
            value = visit_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _coerce_snapshot_value(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _normalize_aptitude_value(self, value: object) -> str:
        return self._coerce_snapshot_value(value) or "En attente"

    def _nested_snapshot_value(self, source: object, *keys: str) -> object:
        current = source
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _ensure_visit_certificates(self, db: Session, visit: MedicalVisit, current_user: User) -> None:
        form_data = self._normalize_incoming_form_data(
            visit.form_data or {},
            worker=visit.worker or self._get_worker(db, visit.worker_id),
            visit_date=visit.visit_date,
            site_name=visit.site_name,
        )
        visit_data = form_data.get("visitData") if isinstance(form_data.get("visitData"), dict) else form_data
        worker_snapshot = self._normalize_worker_snapshot({}, visit.worker or self._get_worker(db, visit.worker_id), form_data, visit.visit_date, visit.site_name)
        if not isinstance(visit_data, dict):
            return

        orientation_snapshot = visit_data.get("orientationCertificates")
        aptitude_snapshot = visit_data.get("aptitudeCertificate") if isinstance(visit_data.get("aptitudeCertificate"), dict) else {}
        validation = visit_data.get("validation") if isinstance(visit_data.get("validation"), dict) else {}
        medical_decision = visit_data.get("medicalDecision") if isinstance(visit_data.get("medicalDecision"), dict) else {}

        self.sync_orientation_certificates_for_visit(
            db,
            visit,
            worker_snapshot,
            orientation_snapshot,
            validation,
            medical_decision,
            current_user,
        )
        self.ensure_aptitude_certificate_for_visit(
            db,
            visit,
            worker_snapshot,
            aptitude_snapshot,
            validation,
            medical_decision,
            current_user,
        )

    def _is_explicit_orientation_snapshot(self, snapshot: object) -> bool:
        if not isinstance(snapshot, dict):
            return False
        return any(
            self._coerce_snapshot_value(snapshot.get(key))
            for key in ("orientationNumber", "orientationDate", "orientationType", "orientationTypeOther", "orientationDetails")
        )

    def _should_create_aptitude_certificate(self, snapshot: dict, medical_decision: dict) -> bool:
        _ = snapshot
        _ = medical_decision
        return True

    def ensure_aptitude_certificate_for_visit(
        self,
        db: Session,
        visit: MedicalVisit,
        worker_snapshot: dict,
        snapshot: dict,
        validation: dict,
        medical_decision: dict,
        current_user: User,
    ) -> None:
        if not self._should_create_aptitude_certificate(snapshot, medical_decision):
            return

        worker = visit.worker or self._get_worker(db, visit.worker_id)
        campaign_id = self._resolve_campaign_id(visit, worker)
        if campaign_id is None or worker is None:
            return

        existing_records = db.scalars(
            select(AptitudeCertificate)
            .where(
                AptitudeCertificate.medical_visit_id == visit.id,
                AptitudeCertificate.deleted_at.is_(None),
            )
            .order_by(AptitudeCertificate.id.asc())
        ).all()
        canonical = existing_records[0] if existing_records else None
        if canonical is not None and (canonical.status in {"validated", "signed", "printed"} or canonical.validated_at is not None):
            raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
        normalized_snapshot = self.normalize_certificate_snapshot(snapshot)
        certificate_number = self._coerce_snapshot_value(
            normalized_snapshot.get("certificateNumber")
            or (canonical.certificate_number if canonical else "")
        )
        if not certificate_number:
            certificate_number = self._generate_aptitude_certificate_number(db, visit.visit_date)
        next_visit = medical_decision.get("nextVisit") if isinstance(medical_decision.get("nextVisit"), dict) else {}
        issue_date = self._to_date(
            self._coerce_snapshot_value(normalized_snapshot.get("aptitudeDate"))
            or validation.get("validationDate")
            or visit.visit_date
        )
        visit_date = self._to_date(
            self._coerce_snapshot_value(normalized_snapshot.get("visitDate"))
            or visit.visit_date
        )
        next_visit_date = self._to_date(next_visit.get("nextVisitDate")) if isinstance(next_visit, dict) else None
        include_signature = bool(
            normalized_snapshot.get("includeValidatorSignature")
            or validation.get("includeValidatorSignature")
        )
        validator_metadata = {
            "validator_id": normalized_snapshot.get("validatorId") or validation.get("validatorId"),
            "validator_name": normalized_snapshot.get("validatorName") or validation.get("validatorName"),
            "validator_role": normalized_snapshot.get("validatorRole") or validation.get("validatorRole"),
            "validated_at": self._parse_snapshot_datetime(
                normalized_snapshot.get("validatedAt") or validation.get("validatedAt")
            ),
            "validator_signature_image_path": normalized_snapshot.get("validatorSignatureImagePath")
            or validation.get("validatorSignatureImagePath"),
        }

        if canonical is None:
            canonical = AptitudeCertificate(
                worker_id=worker.id,
                campaign_id=campaign_id,
                medical_visit_id=visit.id,
                doctor_id=current_user.id if current_user else None,
                certificate_number=certificate_number,
                issue_date=issue_date,
                visit_date=visit_date,
                aptitude=self._normalize_aptitude_value(normalized_snapshot.get("aptitude") or medical_decision.get("aptitude")),
                aptitude_interpretation=self._coerce_snapshot_value(
                    normalized_snapshot.get("aptitudeInterpretation")
                    or self._nested_snapshot_value(medical_decision, "interpretation", "decisionInterpretation")
                ) or None,
                doctor_recommendations=self._coerce_snapshot_value(normalized_snapshot.get("doctorRecommendations")) or None,
                next_visit_date=next_visit_date,
                include_workspace_signature=include_signature,
                validator_id=validator_metadata["validator_id"],
                validator_name=validator_metadata["validator_name"],
                validator_role=validator_metadata["validator_role"],
                validated_at=validator_metadata["validated_at"],
                validator_signature_image_path=validator_metadata["validator_signature_image_path"],
                status="validated" if self._coerce_snapshot_value(normalized_snapshot.get("status")) in {"validated", "signed", "printed"} else "draft",
            )
        else:
            canonical.worker_id = worker.id
            canonical.campaign_id = campaign_id
            canonical.doctor_id = current_user.id if current_user else canonical.doctor_id
            canonical.certificate_number = certificate_number
            canonical.issue_date = issue_date
            canonical.visit_date = visit_date
            canonical.aptitude = self._normalize_aptitude_value(normalized_snapshot.get("aptitude") or medical_decision.get("aptitude"))
            canonical.aptitude_interpretation = self._coerce_snapshot_value(
                normalized_snapshot.get("aptitudeInterpretation")
                or self._nested_snapshot_value(medical_decision, "interpretation", "decisionInterpretation")
            ) or None
            canonical.doctor_recommendations = self._coerce_snapshot_value(normalized_snapshot.get("doctorRecommendations")) or None
            canonical.next_visit_date = next_visit_date
            canonical.include_workspace_signature = include_signature
            canonical.validator_id = validator_metadata["validator_id"]
            canonical.validator_name = validator_metadata["validator_name"]
            canonical.validator_role = validator_metadata["validator_role"]
            canonical.validated_at = validator_metadata["validated_at"]
            canonical.validator_signature_image_path = validator_metadata["validator_signature_image_path"]
            canonical.status = (
                "validated"
                if self._coerce_snapshot_value(normalized_snapshot.get("status")) in {"validated", "signed", "printed"}
                else canonical.status or "draft"
            )

        db.add(canonical)
        db.flush()
        db.refresh(canonical)

    def sync_orientation_certificates_for_visit(
        self,
        db: Session,
        visit: MedicalVisit,
        worker_snapshot: dict,
        orientation_payload: object,
        validation: dict,
        medical_decision: dict,
        current_user: User,
    ) -> None:
        entries = self._extract_orientation_entries(orientation_payload)
        explicit_entries = [entry for entry in entries if self._is_explicit_orientation_snapshot(entry)]
        if not explicit_entries:
            return

        worker = visit.worker or self._get_worker(db, visit.worker_id)
        campaign_id = self._resolve_campaign_id(visit, worker)
        if campaign_id is None or worker is None:
            return

        existing_records = db.scalars(
            select(OrientationCertificate)
            .where(
                OrientationCertificate.medical_visit_id == visit.id,
                OrientationCertificate.deleted_at.is_(None),
            )
            .order_by(OrientationCertificate.id.asc())
        ).all()
        for entry in explicit_entries:
            normalized_entry = self._build_orientation_snapshot(
                entry,
                worker_snapshot,
                medical_decision,
                validation,
                worker,
                {},
            )
            record = self._find_matching_orientation_record(existing_records, normalized_entry)
            if record is not None and (record.status in {"validated", "signed", "printed"} or record.validated_at is not None):
                raise ConflictException("SIGNED_DOCUMENT_IMMUTABLE")
            orientation_number = self._coerce_snapshot_value(
                normalized_entry.get("orientationNumber")
                or (record.orientation_number if record else "")
            )
            if not orientation_number:
                orientation_number = self._generate_orientation_number(db, campaign_id, visit.visit_date)

            if record is None:
                record = OrientationCertificate(
                    worker_id=worker.id,
                    campaign_id=campaign_id,
                    medical_visit_id=visit.id,
                    doctor_id=current_user.id if current_user else None,
                    orientation_number=orientation_number,
                    orientation_date=self._coerce_snapshot_value(normalized_entry.get("orientationDate")) or visit.visit_date,
                    orientation_type=self._coerce_snapshot_value(normalized_entry.get("orientationType")),
                    orientation_types=normalized_entry.get("orientationTypes") if isinstance(normalized_entry.get("orientationTypes"), dict) else None,
                    orientation_type_other=self._coerce_snapshot_value(normalized_entry.get("orientationTypeOther")) or None,
                    orientation_details=self._coerce_snapshot_value(normalized_entry.get("orientationDetails")) or None,
                    doctor_name=self._coerce_snapshot_value(normalized_entry.get("prescribingDoctor")) or None,
                    include_workspace_signature=bool(normalized_entry.get("includeValidatorSignature")),
                    validator_id=normalized_entry.get("validatorId"),
                    validator_name=normalized_entry.get("validatorName"),
                    validator_role=normalized_entry.get("validatorRole"),
                    validated_at=self._parse_snapshot_datetime(normalized_entry.get("validatedAt")),
                    validator_signature_image_path=normalized_entry.get("validatorSignatureImagePath"),
                    status=self._coerce_snapshot_value(normalized_entry.get("status")) or "draft",
                )
            else:
                record.worker_id = worker.id
                record.campaign_id = campaign_id
                record.doctor_id = current_user.id if current_user else record.doctor_id
                record.orientation_number = orientation_number
                record.orientation_date = self._coerce_snapshot_value(normalized_entry.get("orientationDate")) or record.orientation_date
                record.orientation_type = self._coerce_snapshot_value(normalized_entry.get("orientationType"))
                record.orientation_types = normalized_entry.get("orientationTypes") if isinstance(normalized_entry.get("orientationTypes"), dict) else record.orientation_types
                record.orientation_type_other = self._coerce_snapshot_value(normalized_entry.get("orientationTypeOther")) or None
                record.orientation_details = self._coerce_snapshot_value(normalized_entry.get("orientationDetails")) or None
                record.doctor_name = self._coerce_snapshot_value(normalized_entry.get("prescribingDoctor")) or None
                record.include_workspace_signature = bool(normalized_entry.get("includeValidatorSignature"))
                record.validator_id = normalized_entry.get("validatorId")
                record.validator_name = normalized_entry.get("validatorName")
                record.validator_role = normalized_entry.get("validatorRole")
                record.validated_at = self._parse_snapshot_datetime(normalized_entry.get("validatedAt"))
                record.validator_signature_image_path = normalized_entry.get("validatorSignatureImagePath")
                record.status = self._coerce_snapshot_value(normalized_entry.get("status")) or record.status or "draft"

            db.add(record)
            db.flush()
            db.refresh(record)
            if record not in existing_records:
                existing_records.append(record)

    def _extract_orientation_entries(self, payload: object) -> list[dict]:
        if isinstance(payload, list):
            return [self.normalize_certificate_snapshot(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            return [self.normalize_certificate_snapshot(item) for item in payload.get("entries", []) if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [self.normalize_certificate_snapshot(payload)]
        return []

    def _orientation_snapshot_identity(self, snapshot: dict) -> str:
        explicit_id = self._coerce_snapshot_value(snapshot.get("id") or snapshot.get("uuid"))
        if explicit_id:
            return explicit_id
        identity_source = {
            "orientationNumber": self._coerce_snapshot_value(snapshot.get("orientationNumber")),
            "orientationDate": self._coerce_snapshot_value(snapshot.get("orientationDate")),
            "orientationType": self._coerce_snapshot_value(snapshot.get("orientationType")),
            "orientationTypeOther": self._coerce_snapshot_value(snapshot.get("orientationTypeOther")),
            "orientationDetails": self._coerce_snapshot_value(snapshot.get("orientationDetails")),
        }
        return hashlib.sha1(json.dumps(identity_source, sort_keys=True).encode("utf-8")).hexdigest()

    def _orientation_certificate_identity_from_record(self, record: OrientationCertificate) -> str:
        identity_source = {
            "orientationNumber": self._coerce_snapshot_value(record.orientation_number),
            "orientationDate": self._coerce_snapshot_value(record.orientation_date),
            "orientationType": self._coerce_snapshot_value(record.orientation_type),
            "orientationTypeOther": self._coerce_snapshot_value(record.orientation_type_other),
            "orientationDetails": self._coerce_snapshot_value(record.orientation_details),
        }
        return hashlib.sha1(json.dumps(identity_source, sort_keys=True).encode("utf-8")).hexdigest()

    def _find_matching_orientation_record(
        self,
        records: list[OrientationCertificate],
        snapshot: dict,
    ) -> OrientationCertificate | None:
        explicit_identity = self._coerce_snapshot_value(snapshot.get("id") or snapshot.get("uuid"))
        if explicit_identity:
            for record in records:
                if self._coerce_snapshot_value(getattr(record, "uuid", "")) == explicit_identity:
                    return record

        orientation_number = self._coerce_snapshot_value(snapshot.get("orientationNumber"))
        if orientation_number:
            for record in records:
                if self._coerce_snapshot_value(record.orientation_number) == orientation_number:
                    return record

        orientation_date = self._coerce_snapshot_value(snapshot.get("orientationDate"))
        orientation_type = self._coerce_snapshot_value(snapshot.get("orientationType"))
        orientation_type_other = self._coerce_snapshot_value(snapshot.get("orientationTypeOther"))
        orientation_details = self._coerce_snapshot_value(snapshot.get("orientationDetails"))
        for record in records:
            if (
                self._coerce_snapshot_value(record.orientation_date) == orientation_date
                and self._coerce_snapshot_value(record.orientation_type) == orientation_type
                and self._coerce_snapshot_value(record.orientation_type_other) == orientation_type_other
                and self._coerce_snapshot_value(record.orientation_details) == orientation_details
            ):
                return record

        return None

    def _resolve_campaign_id(self, visit: MedicalVisit, worker: Worker | None) -> int | None:
        if visit.campaign_id is not None:
            return visit.campaign_id
        if worker and getattr(worker, "campaign_workers", None):
            campaign_workers = sorted(
                worker.campaign_workers,
                key=lambda item: item.created_at or datetime.min,
                reverse=True,
            )
            if campaign_workers:
                return campaign_workers[0].campaign_id
        return None

    def _generate_orientation_number(self, db: Session, campaign_id: int, visit_date: str) -> str:
        date_part = self._coerce_snapshot_value(visit_date)[:10].replace("-", "")
        if len(date_part) != 8:
            date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        count = (
            db.query(OrientationCertificate)
            .filter(
                OrientationCertificate.campaign_id == campaign_id,
                OrientationCertificate.deleted_at.is_(None),
            )
            .count()
            + 1
        )
        return f"ORI-{campaign_id}-{date_part}-{count:03d}"

    def _generate_aptitude_certificate_number(self, db: Session, visit_date: str) -> str:
        year = self._coerce_snapshot_value(visit_date)[:4]
        if len(year) != 4 or not year.isdigit():
            year = str(datetime.now(timezone.utc).year)
        count = db.query(AptitudeCertificate).filter(AptitudeCertificate.deleted_at.is_(None)).count() + 1
        return f"AP-{year}-{count:04d}"
