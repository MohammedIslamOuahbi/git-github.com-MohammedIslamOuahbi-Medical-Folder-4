from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import SyncSchema


class BranchBase(BaseModel):
    company_id: int
    name: str
    location: str | None = None
    address: str | None = None
    manager_name: str | None = None
    notes: str | None = None


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = None
    location: str | None = None
    address: str | None = None
    manager_name: str | None = None
    notes: str | None = None


class BranchRead(BranchBase, SyncSchema):
    id: int
