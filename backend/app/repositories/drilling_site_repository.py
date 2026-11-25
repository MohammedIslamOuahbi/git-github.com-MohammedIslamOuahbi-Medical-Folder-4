from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.drilling_site import DrillingSite
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class DrillingSiteRepository:
    searchable_fields = ["name", "location", "status"]

    def list(self, db: Session, params: PaginationParams) -> tuple[list[DrillingSite], int]:
        query = select(DrillingSite).where(DrillingSite.deleted_at.is_(None))
        count_query = select(func.count(DrillingSite.id)).where(DrillingSite.deleted_at.is_(None))
        if params.search:
            search_filter = build_search_filter(DrillingSite, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(DrillingSite, params.sort_by or "id", DrillingSite.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, site_id: int) -> DrillingSite | None:
        return db.scalar(select(DrillingSite).where(DrillingSite.id == site_id, DrillingSite.deleted_at.is_(None)))

    def create(self, db: Session, site: DrillingSite) -> DrillingSite:
        db.add(site)
        db.commit()
        db.refresh(site)
        return site

    def update(self, db: Session, site: DrillingSite) -> DrillingSite:
        db.add(site)
        db.commit()
        db.refresh(site)
        return site
