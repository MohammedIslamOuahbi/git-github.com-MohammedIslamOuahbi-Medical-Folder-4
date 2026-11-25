# repositories/aptitude_certificate.py
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from app.models.aptitude_certificate import AptitudeCertificate
from app.models.orientation_certificate import CertificateCounter
from datetime import datetime

class AptitudeCertificateRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, certificate_id: int) -> Optional[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.id == certificate_id,
            AptitudeCertificate.deleted_at.is_(None)
        ).first()
    
    def get_by_certificate_number(self, cert_number: str) -> Optional[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.certificate_number == cert_number,
            AptitudeCertificate.deleted_at.is_(None)
        ).first()
    
    def get_by_worker(self, worker_id: int, skip: int = 0, limit: int = 100) -> List[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.worker_id == worker_id,
            AptitudeCertificate.deleted_at.is_(None)
        ).order_by(desc(AptitudeCertificate.created_at)).offset(skip).limit(limit).all()

    def get_by_medical_visit(self, medical_visit_id: int) -> List[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.medical_visit_id == medical_visit_id,
            AptitudeCertificate.deleted_at.is_(None),
        ).order_by(desc(AptitudeCertificate.updated_at), desc(AptitudeCertificate.id)).all()
    
    def get_by_campaign(self, campaign_id: int, skip: int = 0, limit: int = 100) -> List[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.campaign_id == campaign_id,
            AptitudeCertificate.deleted_at.is_(None)
        ).order_by(desc(AptitudeCertificate.created_at)).offset(skip).limit(limit).all()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[AptitudeCertificate]:
        return self.db.query(AptitudeCertificate).filter(
            AptitudeCertificate.deleted_at.is_(None)
        ).order_by(desc(AptitudeCertificate.created_at)).offset(skip).limit(limit).all()
    
    def create(self, certificate: AptitudeCertificate) -> AptitudeCertificate:
        self.db.add(certificate)
        self.db.commit()
        self.db.refresh(certificate)
        return certificate
    
    def update(self, certificate: AptitudeCertificate) -> AptitudeCertificate:
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
    
    # Counter methods (shared table)
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
    
    def increment_aptitude_counter(self, year: int) -> int:
        counter = self.get_counter_by_year(year)
        if not counter:
            counter = self.create_counter(year)
        
        counter.aptitude_count += 1
        self.db.commit()
        return counter.aptitude_count
