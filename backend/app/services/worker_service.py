from __future__ import annotations

from datetime import datetime, timezone
from datetime import date
import uuid
import hashlib
import json

from sqlalchemy import desc, update as sql_update, select
from sqlalchemy.dialects.postgresql import insert
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException, ConflictException, ForbiddenException
from app.models.local_revision import LocalWriteOperation, LocalEditAttempt, LocalRevision
from app.models.user import User
from app.models.worker import Worker
from app.models.sync_change import SyncChange
from app.models.proof_pending import AuthorizationPolicy, OriginProofRequest
from app.services.medical_visit_service import MedicalVisitService
from app.services.protected_worker_write import apply_worker_update
from app.services.authorization_evidence_service import capture_authorization_execution
from app.repositories.worker_repository import WorkerRepository
from app.schemas.pagination import PaginationParams
from app.schemas.worker import WorkerCreate, WorkerUpdate, WorkerRead
from app.utils.pagination import build_paginated_response


class WorkerService:
    ALLOWED_MEDICAL_FILE_KEYS = {
        "medicalFileNumber",
        "employeeCode",
        "nationalId",
        "lastName",
        "firstName",
        "etat_actual",
        "sex",
        "dateOfBirth",
        "birthPlace",
        "familySituation",
        "phone",
        "originAddress",
        "professionalAddress",
        "direction",
        "position",
        "department",
        "service",
        "workshop",
        "schoolEducation",
        "professionalTraining",
        "professionalQualification",
        "nationalServiceStatus",
        "nationalServiceNotes",
        "chronicDiseaseNotes",
        "bloodGroup",
        "rhesus",
        "congenitalDiseases",
        "generalDiseases",
        "surgicalInterventions",
        "accidents",
        "intoxications",
        "tobacco",
        "chewingTobacco",
        "alcoholism",
        "otherIntoxications",
        "familyHistoryFather",
        "familyHistoryMother",
        "familyHistorySisters",
        "familyHistoryBrothers",
        "familyHistorySpouse",
        "familyHistoryChildrenBoys",
        "familyHistoryChildrenGirls",
        "professionalDiseaseNotes",
        "companyName",
        "siteName",
        "professionalHistory",
        "vaccinations",
        "workAccidents",
        "occupationalDiseases",
        "spontaneousConsultations",
        "clinicalExam",
        "dynamicMedicalTests",
        "confirmationStatus",
        "confirmationDate",
        "confirmationDoctor",
        "confirmationSignature",
        "isLocked",
    }

    def __init__(self) -> None:
        self.repository = WorkerRepository()

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, worker_id: int) -> Worker:
        worker = self.repository.get(db, worker_id)
        if not worker:
            raise NotFoundException("Worker not found")
        return worker

    @staticmethod
    def normalize_text(value: str) -> str:
        return " ".join(value.strip().lower().split())

    @staticmethod
    def sanitize_medical_file_data(value: dict | None) -> dict | None:
        if not isinstance(value, dict):
            return None if value is None else {}
        normalized = dict(value)
        if "etat_actual" not in normalized and normalized.get("etat_actuale") is not None:
            normalized["etat_actual"] = normalized.get("etat_actuale")
        return {
            key: normalized[key]
            for key in WorkerService.ALLOWED_MEDICAL_FILE_KEYS
            if key in normalized
        }

    @staticmethod
    def merge_medical_file_data(
        current: dict | None,
        incoming: dict | None,
    ) -> dict | None:
        current = WorkerService.sanitize_medical_file_data(current)
        incoming = WorkerService.sanitize_medical_file_data(incoming)
        if incoming is None:
            return current
        if current is None:
            return incoming

        merged = {**current, **incoming}
        return merged

    def lookup(self, db: Session, first_name: str, last_name: str, birth_date: date, national_id: str) -> Worker:
        worker = self.repository.lookup_by_identity(db, first_name, last_name, birth_date, national_id)
        if not worker:
            raise NotFoundException("Worker not found")
        return worker

    def lookup_with_history(self, db: Session, first_name: str, last_name: str, birth_date: date, national_id: str) -> dict:
        worker = self.lookup(db, first_name, last_name, birth_date, national_id)
        history = MedicalVisitService().build_lookup_history(db, worker)
        return {"worker": worker, "history": history}

    def create(self, db: Session, payload: WorkerCreate, current_user: User,
               operation_uuid: uuid.UUID) -> WorkerRead:
        if not current_user.is_active:
            raise ForbiddenException("LOCAL_WRITE_ACCESS_DENIED")
        source_user = db.info.get("sync_source_user_uuid")
        if source_user is not None and str(source_user) != str(current_user.uuid):
            raise ForbiddenException("SOURCE_USER_OPERATION_MISMATCH")
        if source_user is None:
            db.info["sync_source_user_uuid"] = current_user.uuid
        for required in ("sync_source_device_uuid", "sync_source_generation_uuid", "sync_source_clinic_uuid"):
            if db.info.get(required) is None:
                raise ForbiddenException("SOURCE_IDENTITY_REQUIRED:" + required)
        request_hash = hashlib.sha256(json.dumps(jsonable_encoder(payload.model_dump()), sort_keys=True,
                                                separators=(",", ":")).encode("utf-8")).hexdigest()
        if db.get(LocalEditAttempt, operation_uuid) is not None:
            raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
        worker_uuid = uuid.uuid4()
        try:
            reserved = db.execute(insert(LocalWriteOperation).values(
                operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
                request_hash=request_hash, entity_type="workers", entity_uuid=worker_uuid,
                result_payload={}, created_at=datetime.now(timezone.utc),
            ).on_conflict_do_nothing(index_elements=[LocalWriteOperation.operation_uuid])
              .returning(LocalWriteOperation.operation_uuid)).scalar_one_or_none()
            if reserved is None:
                previous = db.get(LocalWriteOperation, operation_uuid)
                if (previous is None or previous.actor_user_uuid != current_user.uuid
                        or previous.request_hash != request_hash or previous.entity_type != "workers"):
                    raise ConflictException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
                db.info["local_write_replay"] = True
                return WorkerRead.model_validate((previous.result_payload or {}).get("result", previous.result_payload))
            db.info["local_write_replay"] = False
            national_id = (payload.national_id or "").strip()
            if national_id and self.repository.get_by_national_id(db, national_id):
                raise BadRequestException("National identity number already exists.")
            duplicate = self.repository.lookup_by_identity(
                db, payload.first_name, payload.last_name, payload.birth_date, national_id,
            )
            if duplicate:
                raise ConflictException("Worker already exists", {"worker_id": duplicate.id})
            data = payload.model_dump()
            data["etat_actual"] = data.get("etat_actual") or "present"
            medical_file_status = data.pop("medical_file_status", None)
            if medical_file_status:
                medical_file_data = self.sanitize_medical_file_data(data.get("medical_file_data")) or {}
                medical_file_data["confirmationStatus"] = medical_file_status
                if medical_file_status == "confirmed":
                    medical_file_data["isLocked"] = True
                elif medical_file_status == "draft":
                    medical_file_data["isLocked"] = False
                data["medical_file_data"] = medical_file_data
            if "medical_file_data" in data:
                data["medical_file_data"] = self.sanitize_medical_file_data(data.get("medical_file_data"))
            worker = Worker(uuid=worker_uuid, **data)
            db.info["local_operation_uuid"] = operation_uuid
            db.info["stage3_write_contract"] = True
            db.add(worker)
            db.flush()
            result = WorkerRead.model_validate(worker)
            # P1 records a durable, unsigned proof request in this same
            # transaction.  The transport event UUID is bound later when the
            # outbound projection is created; no signature or network call is
            # performed here.
            change = db.scalar(select(SyncChange).where(SyncChange.operation_uuid == operation_uuid).order_by(SyncChange.id.desc()))
            if change is None or change.revision_uuid is None:
                raise RuntimeError("PROOF_REQUEST_SOURCE_CHANGE_MISSING")
            policy_version = "5A-P1-20261014"
            auth_scope = f"clinic:{change.source_clinic_uuid}:workers:create"
            capture_authorization_execution(db, user=current_user, operation=db.get(LocalWriteOperation, operation_uuid), event=change, permission_code="workers.create", scope=auth_scope, policy_version=policy_version)
            if db.get(AuthorizationPolicy, policy_version) is None:
                db.add(AuthorizationPolicy(policy_version=policy_version, offline_days=7, time_reference="trusted_origin_service", unknown_time_action="review", created_at=datetime.now(timezone.utc)))
            revision = db.get(LocalRevision, change.revision_uuid)
            if db.scalar(select(OriginProofRequest).where(OriginProofRequest.operation_uuid == operation_uuid)) is None:
                db.add(OriginProofRequest(request_uuid=uuid.uuid4(), operation_uuid=operation_uuid, event_uuid=change.change_uuid,
                    content_sha256=change.content_sha256, revision_uuid=change.revision_uuid,
                    parent_revision_uuid=revision.parent_revision_uuid if revision else None, origin_user_uuid=change.source_user_uuid,
                    origin_device_uuid=change.source_device_uuid, clinic_uuid=change.source_clinic_uuid,
                    entity_type=change.entity_type, operation=change.operation, policy_version=policy_version,
                    proof_transport_version=1, status="pending_proof", attempt_count=0,
                    last_reason_code="PROOF_NOT_ISSUED", time_state="time_indeterminate",
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
                db.flush()
                if db.info.get("stage5a_fail_proof_request"):
                    raise RuntimeError("STAGE5A_TEST_FAIL_PROOF_REQUEST")
            operation_row = db.get(LocalWriteOperation, operation_uuid)
            operation_row.result_payload = {**(operation_row.result_payload or {}), "result": jsonable_encoder(result)}
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.info.pop("local_operation_uuid", None)
            db.info.pop("stage3_write_contract", None)
            db.info.pop("authorization_capture_operation_uuid", None)
            db.info.pop("sync_source_user_uuid", None)

    def update(self, db: Session, worker_id: int, payload: WorkerUpdate, current_user: User,
               expected_version: int, operation_uuid: uuid.UUID):
        worker = self.get(db, worker_id)
        updates = payload.model_dump(exclude_unset=True)
        medical_file_status = updates.pop("medical_file_status", None)
        national_id = updates.get("national_id")
        if national_id is not None:
            normalized_national_id = str(national_id).strip()
            if normalized_national_id and self.repository.get_by_national_id(db, normalized_national_id, worker_id):
                raise BadRequestException("National identity number already exists.")
            updates["national_id"] = normalized_national_id or None
        if "medical_file_data" in updates:
            updates["medical_file_data"] = self.merge_medical_file_data(
                worker.medical_file_data,
                updates["medical_file_data"],
            )
        if medical_file_status is not None:
            current_medical_file_data = updates.get("medical_file_data", worker.medical_file_data)
            normalized_medical_file_data = self.sanitize_medical_file_data(current_medical_file_data) or {}
            normalized_medical_file_data["confirmationStatus"] = medical_file_status
            if medical_file_status == "confirmed":
                normalized_medical_file_data["isLocked"] = True
            elif medical_file_status == "draft":
                normalized_medical_file_data["isLocked"] = False
            updates["medical_file_data"] = normalized_medical_file_data
        if "etat_actual" in updates:
            updates["etat_actual"] = updates["etat_actual"] or "present"
        return apply_worker_update(db, current_user, worker, action="update", expected_version=expected_version,
                                   operation_uuid=operation_uuid, attempted_payload=payload.model_dump(exclude_unset=True),
                                   values=updates)

    def delete(self, db: Session, worker_id: int, current_user: User, password: str,
               expected_version: int, operation_uuid: uuid.UUID):
        worker = db.get(Worker, worker_id)
        if worker is None:
            raise NotFoundException("Worker not found")
        if not password:
            raise BadRequestException("Password is required to remove a worker.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Worker was not removed.")
        return apply_worker_update(db, current_user, worker, action="delete", expected_version=expected_version,
                                   operation_uuid=operation_uuid, attempted_payload={"delete": True},
                                   values={"deleted_at": datetime.now(timezone.utc), "is_active": False})

    def tests(self, db: Session, worker_id: int):
        self.get(db, worker_id)
        return self.repository.get_tests(db, worker_id)

    def campaigns(self, db: Session, worker_id: int):
        self.get(db, worker_id)
        return self.repository.get_campaigns(db, worker_id)
    
    def get_last_id(self, db: Session) -> int:
        last_worker = db.query(Worker).order_by(desc(Worker.id)).first()
        return last_worker.id if last_worker else 0

    
    
