from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.schemas.common import SyncSchema


class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    role_code: str | None = None
    phone: str | None = None
    qualification: str | None = None
    signature_png: str | None = None
    signatureImageUrl: str | None = None
    hasSignature: bool = False
    signatureUploadedAt: datetime | None = None
    is_active: bool = True
    permissions_version: int = 1


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    phone: str | None = None
    qualification: str | None = None
    signature_png: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserRead(UserBase, SyncSchema):
    id: int
    last_login: datetime | None = None
    permissions: list[str] = []
