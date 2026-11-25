from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class OrientationTypesPayload(BaseModel):
    specialistAdvice: bool = False
    diagnosticCare: bool = False
    other: bool = False


class OrientationCertificateBase(BaseModel):
    worker_id: int
    campaign_id: int
    medical_visit_id: Optional[int] = None
    doctor_id: Optional[int] = None
    orientation_number: Optional[str] = None
    orientation_date: str
    orientation_type: str
    orientation_types: Optional[OrientationTypesPayload] = Field(
        default=None,
        validation_alias=AliasChoices("orientation_types", "orientationTypes"),
    )
    orientation_type_other: Optional[str] = None
    orientation_details: Optional[str] = None
    worker_name: Optional[str] = None
    doctor_name: Optional[str] = None
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
    status: str = "draft"


class OrientationCertificateCreate(OrientationCertificateBase):
    pass


class OrientationCertificateUpdate(BaseModel):
    worker_id: Optional[int] = None
    campaign_id: Optional[int] = None
    medical_visit_id: Optional[int] = None
    doctor_id: Optional[int] = None
    orientation_number: Optional[str] = None
    orientation_date: Optional[str] = None
    orientation_type: Optional[str] = None
    orientation_types: Optional[OrientationTypesPayload] = Field(
        default=None,
        validation_alias=AliasChoices("orientation_types", "orientationTypes"),
    )
    orientation_type_other: Optional[str] = None
    orientation_details: Optional[str] = None
    worker_name: Optional[str] = None
    doctor_name: Optional[str] = None
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
    status: Optional[str] = None


class OrientationCertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    campaign_id: int
    medical_visit_id: Optional[int] = None
    doctor_id: Optional[int] = None
    orientation_number: str
    orientation_date: str
    orientation_type: str
    orientation_types: Optional[OrientationTypesPayload] = Field(
        default=None,
        validation_alias=AliasChoices("orientation_types", "orientationTypes"),
    )
    orientation_type_other: Optional[str] = None
    orientation_details: Optional[str] = None
    includeValidatorSignature: bool = False
    includeDoctorSignature: Optional[bool] = None
    includeWorkspaceSignature: Optional[bool] = None
    validatorId: Optional[int] = None
    validatorName: Optional[str] = None
    validator_name: Optional[str] = None
    validatorRole: Optional[str] = None
    validator_role: Optional[str] = None
    validatedAt: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    validatorSignatureImagePath: Optional[str] = None
    validator_signature_image_path: Optional[str] = None
    validatorSignatureUrl: Optional[str] = None
    validator_signature_url: Optional[str] = None
    status: str
    worker_name: Optional[str] = None
    doctor_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class OrientationCertificateListResponse(BaseModel):
    items: list[OrientationCertificateResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
