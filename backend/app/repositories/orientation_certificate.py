# repositories/orientation_certificate.py
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, select
from typing import Any, List, Optional
from app.models.orientation_certificate import OrientationCertificate, CertificateCounter
from app.dependencies.database import get_db

from datetime import datetime

from app.schemas.orientation_certificate import OrientationCertificateCreate, OrientationCertificateUpdate

class OrientationCertificateRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def _base_query(self):
        return (
            select(OrientationCertificate)
            .where(OrientationCertificate.deleted_at.is_(None))
            .options(
                joinedload(OrientationCertificate.worker),
                joinedload(OrientationCertificate.doctor),
                joinedload(OrientationCertificate.campaign),
            )
        )
        
    def list(self, db: Session, params: Any | None = None) -> list[OrientationCertificate]:
        query = self._base_query()
        query = query.order_by(
            OrientationCertificate.certificate_date.desc(),
            OrientationCertificate.id.desc(),
        )
        return db.scalars(query).unique().all()

    def get(self, db: Session, certificate_id: int) -> OrientationCertificate | None:
        """Get a single orientation certificate by ID."""
        return db.scalar(
            self._base_query().where(OrientationCertificate.id == certificate_id)
        )

    def get_by_worker_and_campaign(
        self,
        db: Session,
        worker_id: int,
        campaign_id: int,
    ) -> OrientationCertificate | None:
        """Get certificate by worker + campaign (for auto-create check)."""
        return db.scalar(
            self._base_query()
            .where(
                OrientationCertificate.worker_id == worker_id,
                OrientationCertificate.campaign_id == campaign_id,
            )
            .order_by(OrientationCertificate.id.desc())
        )

    def get_last_id(self, db: Session) -> int:
        """Get the last (highest) orientation certificate ID."""
        last = (
            db.query(OrientationCertificate)
            .order_by(OrientationCertificate.id.desc())
            .first()
        )
        return last.id if last else 0

    def create(
        self,
        db: Session,
        data: OrientationCertificateCreate,
        current_user_id: int | None = None,
    ) -> OrientationCertificate:
        certificate = OrientationCertificate(
            **data.model_dump(exclude_unset=True),
            created_by_id=current_user_id,
        )
        db.add(certificate)
        db.commit()
        db.refresh(certificate)
        return self.get(db, certificate.id) or certificate

    def update(
        self,
        db: Session,
        certificate_id: int,
        data: OrientationCertificateUpdate,
        current_user_id: int | None = None,
    ) -> OrientationCertificate:
        certificate = self.get(db, certificate_id)
        if certificate is None:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(certificate, field, value)
        
        certificate.updated_by_id = current_user_id
        db.add(certificate)
        db.commit()
        db.refresh(certificate)
        return certificate

    def delete(
        self,
        db: Session,
        certificate_id: int,
        password: str | None = None,
        current_user: Any | None = None,
    ) -> None:
        certificate = self.get(db, certificate_id)
        if certificate is None:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        from datetime import datetime, timezone
        certificate.deleted_at = datetime.now(timezone.utc)
        certificate.deleted_by_id = current_user.id if current_user else None
        db.add(certificate)
        db.commit()

    def count_for_campaign_on_date(self, db: Session, campaign_id: int, date_value) -> int:
        return (
            db.scalar(
                select(func.count(OrientationCertificate.id)).where(
                    OrientationCertificate.campaign_id == campaign_id,
                    OrientationCertificate.certificate_date == date_value,
                    OrientationCertificate.deleted_at.is_(None),
                )
            )
            or 0
        )


        
    def get(self, db: Session, certificate_id: int) -> OrientationCertificate | None:
        """Get a single orientation certificate by ID."""
        return db.scalar(
            self._base_query().where(OrientationCertificate.id == certificate_id)
        )

    
    def get_by_id(self, certificate_id: int) -> Optional[OrientationCertificate]:
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.id == certificate_id,
            OrientationCertificate.deleted_at.is_(None)
        ).first()
    
    def get_by_orientation_number(self, orientation_number: str) -> Optional[OrientationCertificate]:
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.orientation_number == orientation_number,
            OrientationCertificate.deleted_at.is_(None)
        ).first()
    
    def get_by_worker(self, worker_id: int, skip: int = 0, limit: int = 100) -> List[OrientationCertificate]:
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.worker_id == worker_id,
            OrientationCertificate.deleted_at.is_(None)
        ).order_by(desc(OrientationCertificate.created_at)).offset(skip).limit(limit).all()
    
    def get_by_campaign(self, campaign_id: int, skip: int = 0, limit: int = 100) -> List[OrientationCertificate]:
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.campaign_id == campaign_id,
            OrientationCertificate.deleted_at.is_(None)
        ).order_by(desc(OrientationCertificate.created_at)).offset(skip).limit(limit).all()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[OrientationCertificate]:
        return self.db.query(OrientationCertificate).filter(
            OrientationCertificate.deleted_at.is_(None)
        ).order_by(desc(OrientationCertificate.created_at)).offset(skip).limit(limit).all()
    
    def create(self, certificate: OrientationCertificate) -> OrientationCertificate:
        self.db.add(certificate)
        self.db.commit()
        self.db.refresh(certificate)
        return certificate
    
    def update(self, certificate: OrientationCertificate) -> OrientationCertificate:
        self.db.commit()
        self.db.refresh(certificate)
        return certificate
    
    def soft_delete(self, certificate_id: int) -> bool:
        certificate = self.get_by_id(certificate_id)
        if certificate:
            certificate.deleted_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    # Counter methods
    def get_counter_by_year(self, year: int) -> Optional[CertificateCounter]:
        return self.db.query(CertificateCounter).filter(
            CertificateCounter.year == year
        ).first()
    
    def create_counter(self, year: int) -> CertificateCounter:
        counter = CertificateCounter(year=year, orientation_count=0, aptitude_count=0)
        self.db.add(counter)
        self.db.commit()
        self.db.refresh(counter)
        return counter
    
    def increment_orientation_counter(self, year: int) -> int:
        counter = self.get_counter_by_year(year)
        if not counter:
            counter = self.create_counter(year)
        
        counter.orientation_count += 1
        self.db.commit()
        return counter.orientation_count
    
    def generate_certificate_pdf(
        self,
        db: Session,
        certificate_id: int,
        workspace_settings: dict[str, Any] | None = None,
        include_signature: bool = False,
        signature_png: str | None = None,
    ) -> bytes:
        item = self.get(db, certificate_id)
        return self.pdf_service.generate_pdf(
            item,
            workspace_settings=workspace_settings,
            include_signature=include_signature,
            signature_png=signature_png,
        )
        
    # In OrientationCertificateRepository
    # BROKEN — no filtering
    def list(self, db: Session, **kwargs) -> list[OrientationCertificate]:
        return db.scalars(select(OrientationCertificate)).all()