from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMBase


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMe(ORMBase):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    role_code: str | None = None
    phone: str | None = None
    signature_png: str | None = None
    signatureImageUrl: str | None = None
    hasSignature: bool = False
    signatureUploadedAt: str | None = None
    is_active: bool
    permissions_version: int = 1
    permissions: list[str] = []

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
