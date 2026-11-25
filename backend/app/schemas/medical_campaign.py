from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import SyncSchema


class MedicalCampaignBase(BaseModel):
    company_id: int
    branch_id: int
    drilling_site_id: int | None = None
    title: str
    description: str | None = None
    start_date: date
    end_date: date
    status: str = "draft"


class MedicalCampaignCreate(MedicalCampaignBase):
    pass


class MedicalCampaignUpdate(BaseModel):
    company_id: int | None = None
    branch_id: int | None = None
    drilling_site_id: int | None = None
    title: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None


class CampaignDoctorsAssignRequest(BaseModel):
    doctor_ids: list[int]


class CampaignAssistantsAssignRequest(BaseModel):
    assistant_ids: list[int]


class MedicalCampaignDeleteRequest(BaseModel):
    password: str


class MedicalCampaignRead(MedicalCampaignBase, SyncSchema):
    id: int
    created_by: int | None = None
