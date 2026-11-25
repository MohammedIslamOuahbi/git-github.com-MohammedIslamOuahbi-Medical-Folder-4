from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.medicine import Medicine


class MedicineRepository:
    def base_query(self) -> Select[tuple[Medicine]]:
        return select(Medicine).where(Medicine.deleted_at.is_(None))

    def get(self, db: Session, medicine_id: int) -> Medicine | None:
        return db.scalar(self.base_query().where(Medicine.id == medicine_id))

    def list(self, db: Session, *, active_only: bool = False, limit: int = 20, offset: int = 0) -> tuple[list[Medicine], int]:
        query = self.base_query()
        count_query = select(func.count(Medicine.id)).where(Medicine.deleted_at.is_(None))
        if active_only:
            query = query.where(Medicine.is_active.is_(True))
            count_query = count_query.where(Medicine.is_active.is_(True))
        total = db.scalar(count_query) or 0
        items = db.scalars(query.order_by(Medicine.brand_name.asc()).offset(offset).limit(limit)).all()
        return items, total

    def find_by_identity_keys(self, db: Session, keys: Sequence[str]) -> list[Medicine]:
        if not keys:
            return []
        return db.scalars(self.base_query().where(Medicine.stable_identity_key.in_(list(keys)))).all()

    def update_many(self, db: Session, medicines: Sequence[Medicine]) -> None:
        for item in medicines:
            db.add(item)

