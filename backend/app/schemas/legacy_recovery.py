from __future__ import annotations

from pydantic import BaseModel, Field


class RecoveryCaptureRequest(BaseModel):
    source_kind: str
    logical_key: str = Field(min_length=1, max_length=255)
    profile_id: str = Field(min_length=1, max_length=100)
    source_identity: str | None = Field(default=None, max_length=255)
    format_version: int
    sha256: str = Field(min_length=64, max_length=64)
    raw_payload: str
