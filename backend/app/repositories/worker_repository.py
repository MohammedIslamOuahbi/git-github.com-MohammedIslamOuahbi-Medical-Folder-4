from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.campaign_worker import CampaignWorker
from app.models.worker import Worker
from app.models.worker_test import WorkerTest
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class WorkerRepository:
    searchable_fields = ["employee_number", "national_id", "first_name", "last_name", "job_title", "department"]

    def list(self, db: Session, params: PaginationParams) -> tuple[list[Worker], int]:
        query = select(Worker).where(Worker.deleted_at.is_(None))
        count_query = select(func.count(Worker.id)).where(Worker.deleted_at.is_(None))
        if params.search:
            search_filter = build_search_filter(Worker, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(Worker, params.sort_by or "id", Worker.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        return db.scalars(query.offset(params.offset).limit(params.limit)).all(), db.scalar(count_query) or 0

    def get(self, db: Session, worker_id: int) -> Worker | None:
        return db.scalar(select(Worker).where(Worker.id == worker_id, Worker.deleted_at.is_(None)))

    def get_by_national_id(self, db: Session, national_id: str, exclude_worker_id: int | None = None) -> Worker | None:
        query = select(Worker).where(
            Worker.deleted_at.is_(None),
            Worker.national_id.is_not(None),
            Worker.national_id == national_id,
        )
        if exclude_worker_id is not None:
            query = query.where(Worker.id != exclude_worker_id)
        return db.scalar(query)

    def lookup_by_identity(
        self,
        db: Session,
        first_name: str,
        last_name: str,
        birth_date,
        national_id: str | None,
    ) -> Worker | None:
        query = select(Worker).where(Worker.deleted_at.is_(None))
        if birth_date is not None:
            query = query.where(Worker.birth_date == birth_date)
        if national_id:
            query = query.where(Worker.national_id.is_not(None))
        candidates = db.scalars(query).all()

        normalized_first = self._normalize_text(first_name)
        normalized_last = self._normalize_text(last_name)
        normalized_national = national_id.strip() if national_id else ""

        for candidate in candidates:
            if (
                self._normalize_text(candidate.first_name) == normalized_first
                and self._normalize_text(candidate.last_name) == normalized_last
                and candidate.birth_date == birth_date
                and (candidate.national_id or "").strip() == normalized_national
            ):
                return candidate
        return None

    def find_duplicate(self, db: Session, data: dict) -> Worker | None:
        if data.get("first_name") and data.get("last_name") and data.get("birth_date") and data.get("national_id") is not None:
            return self.lookup_by_identity(
                db,
                str(data["first_name"]),
                str(data["last_name"]),
                data["birth_date"],
                str(data["national_id"]) if data["national_id"] is not None else None,
            )

        conditions = []
        if data.get("employee_number"):
            conditions.append(Worker.employee_number == data["employee_number"])
        if data.get("national_id"):
            conditions.append(Worker.national_id == data["national_id"])
        if data.get("first_name") and data.get("last_name") and data.get("birth_date"):
            conditions.append(
                and_(
                    Worker.first_name == data["first_name"],
                    Worker.last_name == data["last_name"],
                    Worker.birth_date == data["birth_date"],
                )
            )
        if not conditions:
            return None
        return db.scalar(select(Worker).where(Worker.deleted_at.is_(None), or_(*conditions)))

    def get_tests(self, db: Session, worker_id: int) -> list[WorkerTest]:
        return db.scalars(select(WorkerTest).where(WorkerTest.worker_id == worker_id, WorkerTest.deleted_at.is_(None))).all()

    def get_campaigns(self, db: Session, worker_id: int) -> list[CampaignWorker]:
        return db.scalars(select(CampaignWorker).where(CampaignWorker.worker_id == worker_id)).all()

    def create(self, db: Session, worker: Worker) -> Worker:
        db.add(worker)
        db.commit()
        db.refresh(worker)
        return worker

    def update(self, db: Session, worker: Worker) -> Worker:
        db.add(worker)
        db.commit()
        db.refresh(worker)
        return worker

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().lower().split())
