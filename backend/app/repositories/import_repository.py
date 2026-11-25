from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob
from app.models.import_row import ImportRow


class ImportRepository:
    def create_job(self, db: Session, job: ImportJob) -> ImportJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_job(self, db: Session, import_job_id: int) -> ImportJob | None:
        return db.scalar(select(ImportJob).where(ImportJob.id == import_job_id))

    def list_jobs(self, db: Session) -> list[ImportJob]:
        return db.scalars(select(ImportJob).order_by(ImportJob.id.desc())).all()

    def save_rows(self, db: Session, rows: list[ImportRow]) -> list[ImportRow]:
        db.add_all(rows)
        db.commit()
        return rows

    def get_rows(self, db: Session, import_job_id: int) -> list[ImportRow]:
        return db.scalars(select(ImportRow).where(ImportRow.import_job_id == import_job_id)).all()

    def update_job(self, db: Session, job: ImportJob) -> ImportJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def update_rows(self, db: Session, rows: list[ImportRow]) -> list[ImportRow]:
        db.add_all(rows)
        db.commit()
        return rows
