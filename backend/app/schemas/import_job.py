from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMBase


class ImportFieldMappingRequest(BaseModel):
    mapping: dict[str, str]


class ImportConfirmRequest(BaseModel):
    campaign_id: int | None = None


class ImportJobRead(ORMBase):
    id: int
    company_id: int | None = None
    campaign_id: int | None = None
    file_name: str
    original_file_name: str
    file_type: str
    file_size: int
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    mapping_json: dict[str, str] | None = None
    errors_json: dict[str, Any] | None = None
    uploaded_by: int | None = None
    imported_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ImportRowRead(ORMBase):
    id: int
    import_job_id: int
    row_number: int
    raw_data_json: dict
    validation_status: str
    errors_json: dict | None = None
    matched_worker_id: int | None = None
    created_at: datetime
    updated_at: datetime
