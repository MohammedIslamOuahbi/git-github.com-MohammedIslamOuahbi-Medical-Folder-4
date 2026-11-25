from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase, SoftDeleteSchema


class MedicineSearchItem(BaseModel):
    id: int
    registrationNumber: str | None = None
    nationalCode: str | None = None
    brandName: str
    genericName: str | None = None
    strength: str | None = None
    pharmaceuticalForm: str | None = None
    packaging: str | None = None
    laboratory: str | None = None
    country: str | None = None
    isActive: bool
    sourceVersion: str | None = None


class MedicineSearchResponse(BaseModel):
    items: list[MedicineSearchItem]
    total: int


class MedicineRead(SoftDeleteSchema):
    id: int
    registration_number: str | None = None
    national_code: str | None = None
    international_nonproprietary_name: str | None = None
    brand_name: str
    full_name: str | None = None
    pharmaceutical_form: str | None = None
    source_pharmaceutical_form: str | None = None
    strength: str | None = None
    packaging: str | None = None
    list_category: str | None = None
    p1: str | None = None
    p2: str | None = None
    observations: str | None = None
    laboratory: str | None = None
    registration_holder: str | None = None
    country: str | None = None
    medicine_type: str | None = None
    status: str | None = None
    is_active: bool
    is_prescribable: bool
    source_name: str
    source_version: str | None = None
    source_file_name: str | None = None


class MedicineStatusUpdate(BaseModel):
    is_active: bool


class MedicineListItem(ORMBase):
    id: int
    brand_name: str
    international_nonproprietary_name: str | None = None
    strength: str | None = None
    pharmaceutical_form: str | None = None
    laboratory: str | None = None
    is_active: bool
    source_version: str | None = None


class MedicineListResponse(BaseModel):
    items: list[MedicineListItem]
    total: int
    limit: int = Field(default=20)
    offset: int = Field(default=0)
