from __future__ import annotations

from datetime import date, datetime
import uuid as py_uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(ORMBase):
    created_at: datetime
    updated_at: datetime | None = None


class SoftDeleteSchema(TimestampSchema):
    deleted_at: datetime | None = None


class SyncSchema(SoftDeleteSchema):
    uuid: py_uuid.UUID | None = None
    sync_version: int = 1
    sync_status: str = "synced"
    local_id: str | None = None


class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str
    data: T | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    details: dict[str, Any] = {}


class DateRangeFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class PasswordDeleteRequest(BaseModel):
    password: str
