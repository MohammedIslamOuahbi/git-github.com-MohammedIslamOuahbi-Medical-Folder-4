from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field


class AptitudeCertificateBase(BaseModel):
    worker_id: int
    campaign_id: int
    medical_visit_id: Optional[int] = None
    doctor_id: Optional[int] = None
    aptitude: str = Field(..., min_length=1, max_length=50)
    aptitude_interpretation: Optional[str] = None
    doctor_recommendations: Optional[str] = None
    visit_date: Optional[str] = None
    next_visit_date: Optional[str] = None
    includeValidatorSignature: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "includeValidatorSignature",
            "includeDoctorSignature",
            "includeWorkspaceSignature",
            "include_validator_signature",
            "include_doctor_signature",
            "include_workspace_signature",
        ),
    )
    issue_date: Optional[str] = None


class AptitudeCertificateCreate(AptitudeCertificateBase):
    pass


class AptitudeCertificateUpdate(BaseModel):
    medical_visit_id: Optional[int] = None
    aptitude: Optional[str] = Field(None, max_length=50)
    aptitude_interpretation: Optional[str] = None
    doctor_recommendations: Optional[str] = None
    visit_date: Optional[str] = None
    next_visit_date: Optional[str] = None
    validator_id: Optional[int] = None
    validator_name: Optional[str] = None
    
    includeValidatorSignature: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices(
            "includeValidatorSignature",
            "includeDoctorSignature",
            "includeWorkspaceSignature",
            "include_validator_signature",
            "include_doctor_signature",
            "include_workspace_signature",
        ),
    )
    issue_date: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|confirmed|validated|signed|printed|cancelled)$")


class AptitudeCertificateInDB(AptitudeCertificateBase):
    id: int
    certificate_number: str
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    includeDoctorSignature: Optional[bool] = None
    includeWorkspaceSignature: Optional[bool] = None
    validatorId: Optional[int] = None
    validatorName: Optional[str] = None
    validator_name: Optional[str] = None
    validatorRole: Optional[str] = None
    validatedAt: Optional[str] = None
    validatorSignatureImagePath: Optional[str] = None
    validated_by_user_id: Optional[int] = None
    medicalVisitId: Optional[int] = None
    certificateNumber: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    companyName: Optional[str] = None
    jobTitle: Optional[str] = None
    aptitudeInterpretation: Optional[str] = None
    birthDate: Optional[str] = None
    birthPlace: Optional[str] = None
    bloodGroup: Optional[str] = None
    doctorRecommendations: Optional[str] = None
    visitDate: Optional[str] = None
    validatedDoctorName: Optional[str] = None
    validated_doctor_name: Optional[str] = None
    validatorSignatureUrl: Optional[str] = None
    issueDate: Optional[str] = None
    worker_full_name: Optional[str] = None
    doctorName: Optional[str] = None
    doctor_name: Optional[str] = None

    class Config:
        from_attributes = True


class AptitudeCertificateResponse(AptitudeCertificateInDB):
    pass
