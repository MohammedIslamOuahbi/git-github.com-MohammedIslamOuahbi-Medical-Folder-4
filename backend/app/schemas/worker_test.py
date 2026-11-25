from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import SyncSchema


class WorkerTestBase(BaseModel):
    campaign_id: int
    worker_id: int
    test_id: int
    doctor_id: int | None = None
    status: str = "pending"
    result: str | None = None
    notes: str | None = None
    is_normal: bool | None = None
    completed_at: datetime | None = None


class WorkerTestCreate(WorkerTestBase):
    pass


class WorkerTestUpdate(BaseModel):
    doctor_id: int | None = None
    status: str | None = None
    result: str | None = None
    notes: str | None = None
    is_normal: bool | None = None
    completed_at: datetime | None = None


class WorkerTestRead(WorkerTestBase, SyncSchema):
    id: int
