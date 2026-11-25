from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.prescription import Prescription


class PrescriptionRepository:
    def _base_query(self):
        return (
            select(Prescription)
            .where(Prescription.deleted_at.is_(None))
            .options(
                joinedload(Prescription.items),
                joinedload(Prescription.worker),
                joinedload(Prescription.doctor),
                joinedload(Prescription.campaign),
            )
        )

    def list(
        self,
        db: Session,
        worker_id: int | None = None,
        campaign_id: int | None = None,
        medical_visit_id: int | None = None,
    ) -> list[Prescription]:
        query = self._base_query()
        if worker_id is not None:
            query = query.where(Prescription.worker_id == worker_id)
        if campaign_id is not None:
            query = query.where(Prescription.campaign_id == campaign_id)
        if medical_visit_id is not None:
            query = query.where(Prescription.medical_visit_id == medical_visit_id)
        query = query.order_by(Prescription.prescription_date.desc(), Prescription.id.desc())
        return db.scalars(query).unique().all()

    def get(self, db: Session, prescription_id: int) -> Prescription | None:
        return db.scalar(self._base_query().where(Prescription.id == prescription_id))

    def count_for_campaign_on_date(self, db: Session, campaign_id: int, date_value) -> int:
        return (
            db.scalar(
                select(func.count(Prescription.id)).where(
                    Prescription.campaign_id == campaign_id,
                    Prescription.prescription_date == date_value,
                    Prescription.deleted_at.is_(None),
                )
            )
            or 0
        )

    def create(self, db: Session, prescription: Prescription) -> Prescription:
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        return self.get(db, prescription.id) or prescription

    def update(self, db: Session, prescription: Prescription) -> Prescription:
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        return self.get(db, prescription.id) or prescription
