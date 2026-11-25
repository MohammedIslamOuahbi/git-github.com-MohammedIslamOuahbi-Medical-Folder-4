from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class PrescriptionItemBase(BaseModel):
    medication_name: str = Field(min_length=1, max_length=255)
    medicine_id: int | None = None
    brand_name: str | None = None
    generic_name: str | None = None
    strength: str | None = None
    pharmaceutical_form: str | None = None
    dosage: str | None = None
    dose_quantity: str | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    frequency_custom: str | None = None
    duration: str | None = None
    duration_value: str | None = None
    duration_unit: str | None = None
    quantity: str | None = None
    number_of_boxes: str | None = None
    instructions: str | None = None
    sort_order: int | None = None


class PrescriptionItemCreate(PrescriptionItemBase):
    pass


class PrescriptionItemUpdate(BaseModel):
    medication_name: str = Field(min_length=1, max_length=255)
    medicine_id: int | None = None
    brand_name: str | None = None
    generic_name: str | None = None
    strength: str | None = None
    pharmaceutical_form: str | None = None
    dosage: str | None = None
    dose_quantity: str | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    frequency_custom: str | None = None
    duration: str | None = None
    duration_value: str | None = None
    duration_unit: str | None = None
    quantity: str | None = None
    number_of_boxes: str | None = None
    instructions: str | None = None
    sort_order: int | None = None


class PrescriptionItemResponse(PrescriptionItemBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class PrescriptionCreate(BaseModel):
    worker_id: int
    campaign_id: int
    medical_visit_id: int | None = None
    doctor_id: int | None = None
    prescription_number: str | None = None
    prescription_date: date
    diagnosis: str | None = None
    notes: str | None = None
    includeValidatorSignature: bool | None = None
    status: str = "draft"
    items: list[PrescriptionItemCreate] = Field(default_factory=list)


class PrescriptionUpdate(BaseModel):
    medical_visit_id: int | None = None
    doctor_id: int | None = None
    prescription_number: str | None = None
    prescription_date: date | None = None
    diagnosis: str | None = None
    notes: str | None = None
    includeValidatorSignature: bool | None = None
    status: str | None = None
    items: list[PrescriptionItemUpdate] | None = None


class PrescriptionResponse(ORMBase):
    id: int
    worker_id: int
    campaign_id: int
    medical_visit_id: int | None = None
    doctor_id: int | None = None
    prescription_number: str
    prescription_date: date
    diagnosis: str | None = None
    notes: str | None = None
    includeValidatorSignature: bool = False
    validatorId: int | None = None
    validatorName: str | None = None
    validatorRole: str | None = None
    validatedAt: datetime | None = None
    validatorSignatureImagePath: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    worker_name: str | None = None
    doctor_name: str | None = None
    items: list[PrescriptionItemResponse] = Field(default_factory=list)
