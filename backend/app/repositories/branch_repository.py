from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class BranchRepository:
    searchable_fields = ["name", "location", "address"]

    def list(self, db: Session, params: PaginationParams) -> tuple[list[Branch], int]:
        query = select(Branch).where(Branch.deleted_at.is_(None))
        count_query = select(func.count(Branch.id)).where(Branch.deleted_at.is_(None))
        if params.search:
            search_filter = build_search_filter(Branch, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(Branch, params.sort_by or "id", Branch.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, branch_id: int) -> Branch | None:
        return db.scalar(select(Branch).where(Branch.id == branch_id, Branch.deleted_at.is_(None)))

    def create(self, db: Session, branch: Branch) -> Branch:
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return branch

    def update(self, db: Session, branch: Branch) -> Branch:
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return branch
