from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.repositories.medical_test_repository import MedicalTestRepository
from app.schemas.medical_test import MedicalTestCreate, MedicalTestUpdate
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response


class MedicalTestService:
    def __init__(self) -> None:
        self.repository = MedicalTestRepository()

    def list(self, db: Session, params: PaginationParams, active: bool | None = None):
        items, total = self.repository.list(db, params, active=active)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, test_id: int) -> MedicalTest:
        test = self.repository.get(db, test_id)
        if not test:
            raise NotFoundException("Medical test not found")
        return test

    def create(self, db: Session, payload: MedicalTestCreate) -> MedicalTest:
        data = payload.model_dump()
        data["is_active"] = data.pop("is_active", data.pop("active", True))
        data["category"] = data.get("category") or data["section"]
        return self.repository.create(db, MedicalTest(**data))

    def update(self, db: Session, test_id: int, payload: MedicalTestUpdate) -> MedicalTest:
        test = self.get(db, test_id)
        changes = payload.model_dump(exclude_unset=True)
        if "active" in changes and "is_active" not in changes:
            changes["is_active"] = changes.pop("active")
        else:
            changes.pop("active", None)

        if "section" in changes and "category" not in changes:
            changes["category"] = changes["section"]

        for key, value in changes.items():
            setattr(test, key, value)
        test.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, test)

    def delete(self, db: Session, test_id: int, current_user: User, password: str) -> MedicalTest:
        test = self.get(db, test_id)
        if not password:
            raise BadRequestException("Password is required to remove a medical test.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Medical test was not removed.")
        test.is_active = False
        test.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, test)
