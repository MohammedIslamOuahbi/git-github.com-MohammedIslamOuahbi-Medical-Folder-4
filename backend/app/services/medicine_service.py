from __future__ import annotations

import math

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenException, NotFoundException
from app.models.medicine import Medicine
from app.models.user import User
from app.repositories.medicine_repository import MedicineRepository
from app.schemas.medicine import MedicineListResponse, MedicineRead, MedicineSearchItem, MedicineSearchResponse


class MedicineService:
    def __init__(self) -> None:
        self.repository = MedicineRepository()

    def list(self, db: Session, *, active_only: bool = False, limit: int = 20, offset: int = 0) -> MedicineListResponse:
        capped_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        items, total = self.repository.list(db, active_only=active_only, limit=capped_limit, offset=safe_offset)
        return MedicineListResponse(items=items, total=total, limit=capped_limit, offset=safe_offset)

    def get(self, db: Session, medicine_id: int) -> MedicineRead:
        item = self.repository.get(db, medicine_id)
        if item is None:
            raise NotFoundException("Médicament introuvable.")
        return MedicineRead.model_validate(item)

    def search(self, db: Session, *, q: str, limit: int = 20, active_only: bool = True) -> MedicineSearchResponse:
        raw_query = (q or "").strip()
        normalized = self._normalize_search_text(raw_query)
        capped_limit = max(1, min(limit, 50))
        if not normalized or len(normalized) < 2:
            return MedicineSearchResponse(items=[], total=0)

        brand_exact = case((Medicine.normalized_brand_name == normalized, 0), else_=1)
        brand_prefix = case((Medicine.normalized_brand_name.like(f"{normalized}%"), 0), else_=1)
        generic_prefix = case((Medicine.normalized_generic_name.like(f"{normalized}%"), 0), else_=1)
        brand_contains = case((Medicine.normalized_brand_name.like(f"%{normalized}%"), 0), else_=1)
        generic_contains = case((Medicine.normalized_generic_name.like(f"%{normalized}%"), 0), else_=1)
        search_contains = case((func.coalesce(Medicine.search_text, "").like(f"%{normalized}%"), 0), else_=1)

        query = select(Medicine).where(Medicine.deleted_at.is_(None))
        if active_only:
            query = query.where(Medicine.is_active.is_(True), Medicine.is_prescribable.is_(True))
        query = query.where(
            or_(
                Medicine.normalized_brand_name.like(f"%{normalized}%"),
                Medicine.normalized_generic_name.like(f"%{normalized}%"),
                func.coalesce(Medicine.registration_number, "").ilike(f"%{raw_query}%"),
                func.coalesce(Medicine.national_code, "").ilike(f"%{raw_query}%"),
                func.coalesce(Medicine.search_text, "").like(f"%{normalized}%"),
            )
        ).order_by(
            brand_exact.asc(),
            brand_prefix.asc(),
            generic_prefix.asc(),
            brand_contains.asc(),
            generic_contains.asc(),
            search_contains.asc(),
            Medicine.brand_name.asc(),
        ).limit(capped_limit)

        items = db.scalars(query).all()
        return MedicineSearchResponse(
            items=[
                MedicineSearchItem(
                    id=item.id,
                    registrationNumber=item.registration_number,
                    nationalCode=item.national_code,
                    brandName=item.brand_name,
                    genericName=item.international_nonproprietary_name,
                    strength=item.strength,
                    pharmaceuticalForm=item.pharmaceutical_form,
                    packaging=item.packaging,
                    laboratory=item.laboratory,
                    country=item.country,
                    isActive=item.is_active,
                    sourceVersion=item.source_version,
                )
                for item in items
            ],
            total=len(items),
        )

    def update_status(self, db: Session, medicine_id: int, *, is_active: bool, current_user: User) -> MedicineRead:
        if (current_user.role or "").strip().lower() not in {"super_admin", "admin"}:
            raise ForbiddenException("Vous n'êtes pas autorisé à modifier le catalogue des médicaments.")
        item = self.repository.get(db, medicine_id)
        if item is None:
            raise NotFoundException("Médicament introuvable.")
        item.is_active = is_active
        db.add(item)
        db.commit()
        db.refresh(item)
        return MedicineRead.model_validate(item)

    def _normalize_search_text(self, value: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFD", value or "")
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
        return normalized
