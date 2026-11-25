from __future__ import annotations

from datetime import datetime
import uuid as py_uuid
from pydantic import BaseModel, ConfigDict


class MedicalVisitBase(BaseModel):
    worker_id: int | None = None
    worker_uuid: py_uuid.UUID | None = None
    campaign_id: int | None = None
    campaign_uuid: py_uuid.UUID | None = None
    visit_date: str
    site_name: str | None = None
    status: str = "draft"
    form_data: dict | None = None
    doctor_notes: str | None = None


class MedicalVisitCreate(MedicalVisitBase):
    pass


class MedicalVisitDuplicateRequest(BaseModel):
    campaign_id: int
    company_name: str | None = None
    branch_name: str | None = None
    site_name: str | None = None
    campaign_name: str | None = None


class MedicalVisitUpdate(BaseModel):
    visit_date: str | None = None
    site_name: str | None = None
    status: str | None = None
    form_data: dict | None = None
    doctor_notes: str | None = None
    updated_by: int | None = None


class MedicalVisitStatusUpdate(BaseModel):
    status: str


class MedicalVisitValidateRequest(BaseModel):
    doctor_notes: str | None = None


class MedicalVisitRead(MedicalVisitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: py_uuid.UUID
    created_by: int | None = None
    updated_by: int | None = None
    validated_by: int | None = None
    validated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    sync_status: str
    last_synced_at: datetime | None = None
    version: int
