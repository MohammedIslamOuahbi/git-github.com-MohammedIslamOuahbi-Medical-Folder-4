from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator

from app.schemas.common import SyncSchema


def _normalize_medical_file_data(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if "dynamicMedicalTests" in value and not isinstance(value["dynamicMedicalTests"], dict):
        raise ValueError("dynamicMedicalTests must be an object.")
    if "etat_actual" not in value and value.get("etat_actuale") is not None:
        value = {**value, "etat_actual": value.get("etat_actuale")}
    return value


class WorkerBase(BaseModel):
    company_id: int
    branch_id: int
    drilling_site_id: int | None = None
    employee_number: str
    national_id: str | None = None
    first_name: str
    last_name: str
    gender: str | None = None
    birth_date: date | None = None
    birth_wilaya: str | None = None
    marital_status: str | None = None
    blood_group: str | None = None
    phone: str | None = None
    emergency_phone: str | None = None
    address: str | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    medical_status: str | None = None
    medical_file_status: str | None = None
    etat_actual: str = "present"
    medical_file_data: dict[str, Any] | None = None
    photo: str | None = None
    is_active: bool = True

    @field_validator("medical_file_data")
    @classmethod
    def validate_medical_file_data(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _normalize_medical_file_data(value)


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    company_id: int | None = None
    branch_id: int | None = None
    drilling_site_id: int | None = None
    employee_number: str | None = None
    national_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    birth_wilaya: str | None = None
    marital_status: str | None = None
    blood_group: str | None = None
    phone: str | None = None
    emergency_phone: str | None = None
    address: str | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    medical_status: str | None = None
    medical_file_status: str | None = None
    etat_actual: str | None = None
    medical_file_data: dict[str, Any] | None = None
    photo: str | None = None
    is_active: bool | None = None

    @field_validator("medical_file_data")
    @classmethod
    def validate_medical_file_data(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _normalize_medical_file_data(value)


class WorkerRead(WorkerBase, SyncSchema):
    id: int
    campaign_status: str | None = None
    medical_file_status: str | None = None
    latest_visit_date: str | None = None
    latest_visit_id: int | None = None
