from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.medicine_import import MedicineImport, MedicineImportError


class MedicineImportRepository:
    def create(self, db: Session, item: MedicineImport) -> MedicineImport:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update(self, db: Session, item: MedicineImport) -> MedicineImport:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def get(self, db: Session, import_id: int) -> MedicineImport | None:
        return db.scalar(select(MedicineImport).where(MedicineImport.id == import_id))

    def list(self, db: Session) -> list[MedicineImport]:
        return db.scalars(select(MedicineImport).order_by(MedicineImport.created_at.desc())).all()

    def get_by_hash(self, db: Session, file_hash: str) -> MedicineImport | None:
        return db.scalar(select(MedicineImport).where(MedicineImport.file_hash == file_hash))

    def replace_errors(self, db: Session, import_id: int, errors: list[MedicineImportError]) -> None:
        existing = db.scalars(
            select(MedicineImportError).where(MedicineImportError.medicine_import_id == import_id)
        ).all()
        for item in existing:
            db.delete(item)
        for error in errors:
            db.add(error)

    def list_errors(self, db: Session, import_id: int) -> list[MedicineImportError]:
        return db.scalars(
            select(MedicineImportError)
            .where(MedicineImportError.medicine_import_id == import_id)
            .order_by(MedicineImportError.row_number.asc(), MedicineImportError.id.asc())
        ).all()
