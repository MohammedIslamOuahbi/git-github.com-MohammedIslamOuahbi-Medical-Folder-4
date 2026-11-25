from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.models.drilling_site import DrillingSite
from app.models.user import User
from app.repositories.drilling_site_repository import DrillingSiteRepository
from app.schemas.drilling_site import DrillingSiteCreate, DrillingSiteUpdate
from app.schemas.pagination import PaginationParams
from app.utils.pagination import build_paginated_response


class DrillingSiteService:
    def __init__(self) -> None:
        self.repository = DrillingSiteRepository()

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, site_id: int) -> DrillingSite:
        site = self.repository.get(db, site_id)
        if not site:
            raise NotFoundException("Drilling site not found")
        return site

    def create(self, db: Session, payload: DrillingSiteCreate, *, trusted_uuid=None) -> DrillingSite:
        data = payload.model_dump()
        return self.repository.create(db, DrillingSite(**data, uuid=trusted_uuid) if trusted_uuid else DrillingSite(**data))

    def update(self, db: Session, site_id: int, payload: DrillingSiteUpdate) -> DrillingSite:
        site = self.get(db, site_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(site, key, value)
        site.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, site)

    def delete(self, db: Session, site_id: int, current_user: User, password: str) -> DrillingSite:
        site = self.get(db, site_id)
        if not password:
            raise BadRequestException("Password is required to remove a drilling site.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. Drilling site was not removed.")
        site.deleted_at = datetime.now(timezone.utc)
        return self.repository.update(db, site)
