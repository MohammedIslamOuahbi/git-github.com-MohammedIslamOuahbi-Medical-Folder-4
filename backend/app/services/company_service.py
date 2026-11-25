from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.models.company import Company
from app.models.user import User
from app.models.local_revision import LocalWriteOperation
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response


class CompanyService:
    def __init__(self) -> None:
        self.repository = CompanyRepository()

    def _validate_contract_dates(self, contract_start_date, contract_end_date) -> None:
        if contract_start_date and contract_end_date and contract_end_date < contract_start_date:
            raise BadRequestException("La date de fin du contrat doit etre posterieure ou egale a la date de debut.")

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, company_id: int) -> Company:
        company = self.repository.get(db, company_id)
        if not company:
            raise NotFoundException("Company not found")
        return company

    def create(self, db: Session, payload: CompanyCreate, current_user: User, operation_uuid: uuid.UUID, *, trusted_uuid: uuid.UUID | None = None) -> Company:
        data = payload.model_dump()
        self._validate_contract_dates(data.get("contract_start_date"), data.get("contract_end_date"))
        company = Company(**data, uuid=trusted_uuid or uuid.uuid4())
        request_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        existing = db.get(LocalWriteOperation, operation_uuid)
        if existing:
            if existing.request_hash != request_hash or existing.entity_type != "companies":
                raise BadRequestException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            return self.get(db, existing.entity_uuid)
        db.add(LocalWriteOperation(operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
            request_hash=request_hash, entity_type="companies", entity_uuid=company.uuid,
            result_payload={}, created_at=datetime.now(timezone.utc)))
        db.info["local_operation_uuid"] = operation_uuid; db.info["stage3_write_contract"] = True; db.flush()
        try:
            result = self.repository.create(db, company)
            db.execute(LocalWriteOperation.__table__.update().where(LocalWriteOperation.operation_uuid == operation_uuid).values(result_payload={"id": result.id, "uuid": str(result.uuid)}))
            db.commit(); return result
        finally:
            db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)

    def update(self, db: Session, company_id: int, payload: CompanyUpdate, current_user: User, operation_uuid: uuid.UUID) -> Company:
        company = self.get(db, company_id)
        next_contract_start = payload.contract_start_date if payload.contract_start_date is not None else company.contract_start_date
        next_contract_end = payload.contract_end_date if payload.contract_end_date is not None else company.contract_end_date
        self._validate_contract_dates(next_contract_start, next_contract_end)
        changes = payload.model_dump(exclude_unset=True)
        request_hash = hashlib.sha256(json.dumps(changes, sort_keys=True, default=str).encode()).hexdigest()
        existing = db.get(LocalWriteOperation, operation_uuid)
        if existing:
            if existing.request_hash != request_hash or existing.entity_type != "companies" or existing.entity_uuid != company.uuid:
                raise BadRequestException("OPERATION_UUID_REUSED_WITH_DIFFERENT_CONTENT")
            return company
        db.add(LocalWriteOperation(operation_uuid=operation_uuid, actor_user_uuid=current_user.uuid,
            request_hash=request_hash, entity_type="companies", entity_uuid=company.uuid,
            result_payload={}, created_at=datetime.now(timezone.utc)))
        db.info["local_operation_uuid"] = operation_uuid; db.info["stage3_write_contract"] = True; db.flush()
        for key, value in changes.items():
            setattr(company, key, value)
        company.updated_at = datetime.now(timezone.utc)
        try:
            result = self.repository.update(db, company)
            db.execute(LocalWriteOperation.__table__.update().where(LocalWriteOperation.operation_uuid == operation_uuid).values(result_payload={"id": result.id, "uuid": str(result.uuid)}))
            db.commit(); return result
        finally:
            db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)

    def delete(self, db: Session, company_id: int, current_user: User, password: str) -> Company:
        company = self.get(db, company_id)
        if not password:
            raise BadRequestException("Password is required to remove a company.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Company was not removed.")
        company.deleted_at = datetime.now(timezone.utc)
        return self.repository.update(db, company)
