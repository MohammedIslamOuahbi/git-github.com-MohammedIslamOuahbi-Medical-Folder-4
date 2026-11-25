from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditLog
from app.schemas.pagination import PaginationParams


class AuditRepository:
    def list(self, db: Session, params: PaginationParams) -> tuple[list[AuditLog], int]:
        query = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.id.desc())
        count_query = select(func.count(AuditLog.id))
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, audit_log_id: int) -> AuditLog | None:
        return db.scalar(select(AuditLog).options(selectinload(AuditLog.user)).where(AuditLog.id == audit_log_id))
