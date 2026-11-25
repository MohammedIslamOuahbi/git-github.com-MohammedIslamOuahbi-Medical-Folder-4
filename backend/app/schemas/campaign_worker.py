from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import TimestampSchema


class CampaignWorkerCreate(BaseModel):
    worker_id: int


class CampaignWorkersAssignRequest(BaseModel):
    worker_ids: list[int]


class CampaignWorkerRead(TimestampSchema):
    id: int
    campaign_id: int
    worker_id: int
    added_by: int | None = None
    status: str
