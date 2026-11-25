from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import SyncSchema


class DrillingSiteBase(BaseModel):
    company_id: int
    branch_id: int
    name: str
    location: str | None = None
    status: str = "active"
    notes: str | None = None


class DrillingSiteCreate(DrillingSiteBase):
    pass


class DrillingSiteUpdate(BaseModel):
    company_id: int | None = None
    branch_id: int | None = None
    name: str | None = None
    location: str | None = None
    status: str | None = None
    notes: str | None = None


class DrillingSiteRead(DrillingSiteBase, SyncSchema):
    id: int
