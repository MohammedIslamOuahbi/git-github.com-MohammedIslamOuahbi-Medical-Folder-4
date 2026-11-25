from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel, Field


class SyncTransportReceiveRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    source_clinic_uuid: uuid.UUID
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
    events: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
    limit: int = Field(default=100, ge=1, le=1000)
    publisher_device_uuid: uuid.UUID
    publisher_generation_uuid: uuid.UUID
    publisher_clinic_uuid: uuid.UUID

class SyncTransportAckRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    event_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
    lease_token: uuid.UUID
    publisher_device_uuid: uuid.UUID
    publisher_generation_uuid: uuid.UUID
    publisher_clinic_uuid: uuid.UUID

class SyncTransportPullRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    source_clinic_uuid: uuid.UUID
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
    limit: int = Field(default=100, ge=1, le=1000)
    after_sequence: int = Field(default=0, ge=0)
    publisher_device_uuid: uuid.UUID
    publisher_generation_uuid: uuid.UUID
    publisher_clinic_uuid: uuid.UUID

class SyncTransportCursorRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
    publisher_device_uuid: uuid.UUID
    publisher_generation_uuid: uuid.UUID
    publisher_clinic_uuid: uuid.UUID

class OriginProofReceiveRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    proof_uuid: uuid.UUID
    event_uuid: uuid.UUID
    content_sha256: str = Field(min_length=64, max_length=64)
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    source_clinic_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
    proof: dict[str, Any]

class OriginProofAckRequest(BaseModel):
    contract_version: str = Field(default="2.1", pattern=r"^2\.1$")
    proof_uuid: uuid.UUID
    receipt_uuid: uuid.UUID
    source_device_uuid: uuid.UUID
    source_generation_uuid: uuid.UUID
    channel: str = Field(min_length=1, max_length=40)
