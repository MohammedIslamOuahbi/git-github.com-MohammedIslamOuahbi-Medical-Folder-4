from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship, synonym

from app.database import Base, SyncMetadataMixin

class AptitudeCertificate(Base, SyncMetadataMixin):
    __tablename__ = "aptitude_certificates"
    __table_args__ = (UniqueConstraint("medical_visit_id", name="uq_aptitude_certificates_medical_visit_id"),)
    
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("medical_campaigns.id"), nullable=False)
    medical_visit_id = Column(Integer, ForeignKey("medical_visits.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    certificate_number = Column(String(20), unique=True, nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    visit_date = Column(Date, nullable=True)
    next_visit_date = Column(Date, nullable=True)
    
    aptitude = Column(String(50), nullable=False)
    aptitude_interpretation = Column(Text, nullable=True)
    doctor_recommendations = Column(Text, nullable=True)
    
    include_workspace_signature = Column(Boolean, default=False)
    validator_id = Column(Integer, nullable=True)
    validator_name = Column(String(255), nullable=True)
    validator_role = Column(String(100), nullable=True)
    validated_at = Column(DateTime, nullable=True)
    validator_signature_image_path = Column(String(500), nullable=True)
    status = Column(String(20), default="draft")
    includeValidatorSignature = synonym("include_workspace_signature")
    includeDoctorSignature = synonym("include_workspace_signature")
    includeWorkspaceSignature = synonym("include_workspace_signature")
    include_validator_signature = synonym("include_workspace_signature")
    validatorId = synonym("validator_id")
    validatorName = synonym("validator_name")
    validatorRole = synonym("validator_role")
    validatedAt = synonym("validated_at")
    validatorSignatureImagePath = synonym("validator_signature_image_path")
    validated_by_user_id = synonym("validator_id")
    validated_by_user_name = synonym("validator_name")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    worker = relationship("Worker", back_populates="aptitude_certificates")
    campaign = relationship("MedicalCampaign", back_populates="aptitude_certificates")
    medical_visit = relationship("MedicalVisit", back_populates="aptitude_certificates")
    doctor = relationship("User", back_populates="aptitude_certificates_signed")
