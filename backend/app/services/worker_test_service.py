from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.exceptions import NotFoundException
from app.models.worker_test import WorkerTest
from app.repositories.worker_test_repository import WorkerTestRepository
from app.schemas.pagination import PaginationParams
from app.schemas.worker_test import WorkerTestCreate, WorkerTestUpdate
from app.utils.pagination import build_paginated_response


class WorkerTestService:
    def __init__(self) -> None:
        self.repository = WorkerTestRepository()

    def list(self, db: Session, params: PaginationParams):
        items, total = self.repository.list(db, params)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, worker_test_id: int) -> WorkerTest:
        worker_test = self.repository.get(db, worker_test_id)
        if not worker_test:
            raise NotFoundException("Worker test not found")
        return worker_test

    def create(self, db: Session, payload: WorkerTestCreate) -> WorkerTest:
        return self.repository.create(db, WorkerTest(**payload.model_dump()))

    def update(self, db: Session, worker_test_id: int, payload: WorkerTestUpdate) -> WorkerTest:
        worker_test = self.get(db, worker_test_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(worker_test, key, value)
        worker_test.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, worker_test)
