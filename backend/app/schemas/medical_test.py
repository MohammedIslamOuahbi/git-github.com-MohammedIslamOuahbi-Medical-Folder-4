from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.schemas.common import ORMBase


class MedicalTestBase(BaseModel):
    name: str
    section: str
    category: str | None = None
    description: str | None = None
    normal_range: str | None = None
    unit: str | None = None
    requires_doctor_review: bool = False
    active: bool = True
    is_active: bool | None = None

    @model_validator(mode="after")
    def sync_active_flags(self):
        if self.is_active is not None:
            self.active = self.is_active
        else:
            self.is_active = self.active

        if not self.category:
            self.category = self.section

        return self


class MedicalTestCreate(MedicalTestBase):
    pass


class MedicalTestUpdate(BaseModel):
    name: str | None = None
    section: str | None = None
    category: str | None = None
    description: str | None = None
    normal_range: str | None = None
    unit: str | None = None
    requires_doctor_review: bool | None = None
    active: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def sync_active_flags(self):
        if self.is_active is None and self.active is not None:
            self.is_active = self.active
        if self.active is None and self.is_active is not None:
            self.active = self.is_active
        return self


class MedicalTestRead(MedicalTestBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
