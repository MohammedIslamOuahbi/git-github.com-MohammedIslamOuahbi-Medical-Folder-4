from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.models.branch import Branch
from app.models.user import User
from app.repositories.branch_repository import BranchRepository
from app.schemas.branch import BranchCreate, BranchUpdate
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response


class BranchService:
    def __init__(self) -> None:
        self.repository = BranchRepository()

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, branch_id: int) -> Branch:
        branch = self.repository.get(db, branch_id)
        if not branch:
            raise NotFoundException("Branch not found")
        return branch

    def create(self, db: Session, payload: BranchCreate, *, trusted_uuid=None) -> Branch:
        data = payload.model_dump()
        return self.repository.create(db, Branch(**data, uuid=trusted_uuid) if trusted_uuid else Branch(**data))

    def update(self, db: Session, branch_id: int, payload: BranchUpdate) -> Branch:
        branch = self.get(db, branch_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(branch, key, value)
        branch.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, branch)

    def delete(self, db: Session, branch_id: int, current_user: User, password: str) -> Branch:
        branch = self.get(db, branch_id)
        if not password:
            raise BadRequestException("Password is required to remove a branch.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Branch was not removed.")
        branch.deleted_at = datetime.now(timezone.utc)
        return self.repository.update(db, branch)
