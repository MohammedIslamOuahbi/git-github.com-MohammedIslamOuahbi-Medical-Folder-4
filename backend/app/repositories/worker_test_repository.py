from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.worker_test import WorkerTest
from app.schemas.pagination import PaginationParams


class WorkerTestRepository:
    def list(self, db: Session, params: PaginationParams) -> tuple[list[WorkerTest], int]:
        query = select(WorkerTest).where(WorkerTest.deleted_at.is_(None))
        count_query = select(func.count(WorkerTest.id)).where(WorkerTest.deleted_at.is_(None))
        sort_column = getattr(WorkerTest, params.sort_by or "id", WorkerTest.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, worker_test_id: int) -> WorkerTest | None:
        return db.scalar(select(WorkerTest).where(WorkerTest.id == worker_test_id, WorkerTest.deleted_at.is_(None)))

    def create(self, db: Session, worker_test: WorkerTest) -> WorkerTest:
        db.add(worker_test)
        db.commit()
        db.refresh(worker_test)
        return worker_test

    def update(self, db: Session, worker_test: WorkerTest) -> WorkerTest:
        db.add(worker_test)
        db.commit()
        db.refresh(worker_test)
        return worker_test
