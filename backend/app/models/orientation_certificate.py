# models/orientation_certificate.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, func, JSON
from sqlalchemy.orm import relationship, synonym
from datetime import datetime
from app.database import Base, SyncMetadataMixin

class OrientationCertificate(Base, SyncMetadataMixin):
    __tablename__ = "orientation_certificates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign keys
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("medical_campaigns.id"), nullable=False)
    medical_visit_id = Column(Integer, ForeignKey("medical_visits.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Certificate info
    orientation_number = Column(String(50), nullable=False, unique=True)
    orientation_date = Column(String(10), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d"))
    orientation_type = Column(String(50), nullable=False)
    orientation_types = Column(JSON, nullable=True, default=dict)
    orientation_type_other = Column(Text, nullable=True)
    orientation_details = Column(Text, nullable=True)
    
    # Signature & status
    doctor_name = Column(String(100), nullable=True)
    include_workspace_signature = Column(Boolean, default=False)
    validator_id = Column(Integer, nullable=True)
    validator_name = Column(String(255), nullable=True)
    validator_role = Column(String(100), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validator_signature_image_path = Column(String(500), nullable=True)
    status = Column(String(20), default="draft")
    includeValidatorSignature = synonym("include_workspace_signature")
    includeDoctorSignature = synonym("include_workspace_signature")
    includeWorkspaceSignature = synonym("include_workspace_signature")
    validatorId = synonym("validator_id")
    validatorName = synonym("validator_name")
    validatorRole = synonym("validator_role")
    validatedAt = synonym("validated_at")
    validatorSignatureImagePath = synonym("validator_signature_image_path")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships (optional)
    worker = relationship("Worker", back_populates="orientation_certificates")
    campaign = relationship("MedicalCampaign", back_populates="orientation_certificates")
    medical_visit = relationship("MedicalVisit", back_populates="orientation_certificates")
    doctor = relationship("User", back_populates="orientation_certificates_signed")
    
class CertificateCounter(Base):
    __tablename__ = "certificate_counters"
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, unique=True)
    orientation_count = Column(Integer, default=0)
    aptitude_count = Column(Integer, default=0)
