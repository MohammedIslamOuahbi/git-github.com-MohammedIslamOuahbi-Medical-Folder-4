from datetime import datetime
from pydantic import BaseModel
from app.schemas.medical_test import MedicalTestRead


class CampaignTestBase(BaseModel):
    test_id: int
    required: bool = False


class CampaignTestCreate(CampaignTestBase):
    pass


class CampaignTestUpdate(CampaignTestBase):
    pass


class CampaignTestResponse(CampaignTestBase):
    id: int
    campaign_test_id: int
    campaign_id: int
    name: str | None = None
    description: str | None = None
    type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    test: MedicalTestRead | None = None

    class Config:
        from_attributes = True
