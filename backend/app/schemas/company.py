from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr

from app.schemas.common import SyncSchema


class CompanyBase(BaseModel):
    name: str
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contact_person: str | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contact_person: str | None = None
    notes: str | None = None


class CompanyRead(CompanyBase, SyncSchema):
    id: int
