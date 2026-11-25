from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.medical_test import MedicalTest
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class MedicalTestRepository:
    searchable_fields = ["name", "section", "category", "description", "normal_range", "unit"]

    def list(self, db: Session, params: PaginationParams, active: bool | None = None) -> tuple[list[MedicalTest], int]:
        query = select(MedicalTest)
        count_query = select(func.count(MedicalTest.id))
        if active is not None:
            query = query.where(MedicalTest.is_active == active)
            count_query = count_query.where(MedicalTest.is_active == active)
        if params.search:
            search_filter = build_search_filter(MedicalTest, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(MedicalTest, params.sort_by or "id", MedicalTest.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, test_id: int) -> MedicalTest | None:
        return db.scalar(select(MedicalTest).where(MedicalTest.id == test_id))

    def create(self, db: Session, test: MedicalTest) -> MedicalTest:
        db.add(test)
        db.commit()
        db.refresh(test)
        return test

    def update(self, db: Session, test: MedicalTest) -> MedicalTest:
        db.add(test)
        db.commit()
        db.refresh(test)
        return test
