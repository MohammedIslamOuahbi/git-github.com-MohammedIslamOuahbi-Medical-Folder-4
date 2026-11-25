from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class CompanyRepository:
    searchable_fields = ["name", "email", "phone", "contact_person"]

    def list(self, db: Session, params: PaginationParams) -> tuple[list[Company], int]:
        query = select(Company).where(Company.deleted_at.is_(None))
        count_query = select(func.count(Company.id)).where(Company.deleted_at.is_(None))
        if params.search:
            search_filter = build_search_filter(Company, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(Company, params.sort_by or "id", Company.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, company_id: int) -> Company | None:
        return db.scalar(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)))

    def create(self, db: Session, company: Company) -> Company:
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    def update(self, db: Session, company: Company) -> Company:
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
