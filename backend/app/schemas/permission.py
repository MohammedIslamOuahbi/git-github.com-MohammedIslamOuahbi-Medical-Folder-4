from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class PermissionRead(ORMBase):
    id: int
    module: str
    action: str
    code: str
    name: str
    description: str | None = None
    category: str | None = None
    is_sensitive: bool
    is_system: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class RoleSummary(ORMBase):
    id: int
    name: str
    code: str
    description: str | None = None
    is_system: bool
    is_active: bool


class RolePermissionMatrix(BaseModel):
    role: RoleSummary
    permissions: list[PermissionRead]
    assigned_permission_codes: list[str]


class RolePermissionUpdateRequest(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class PermissionOverrideUpdateItem(BaseModel):
    permission_code: str
    state: Literal["inherit", "allow", "deny"]


class UserPermissionUpdateRequest(BaseModel):
    permissions: list[PermissionOverrideUpdateItem] = Field(default_factory=list)
    reason: str | None = None


class UserPermissionCopyRequest(BaseModel):
    source_user_id: int
    copy_role: bool = False
    copy_overrides: bool = True
    reason: str | None = None


class EffectivePermissionRead(ORMBase):
    id: int
    code: str
    module: str
    action: str
    name: str
    description: str | None = None
    category: str | None = None
    is_sensitive: bool
    role_allowed: bool
    override: Literal["allow", "deny"] | None = None
    effective_allowed: bool
    source: Literal["user_allow", "user_deny", "role", "default_deny"]
    can_manage: bool


class UserPermissionMatrix(BaseModel):
    user: dict
    permissions_version: int
    direct_override_count: int
    effective_permission_count: int
    is_last_active_super_admin: bool
    permissions: list[EffectivePermissionRead]


class MyPermissionsRead(BaseModel):
    role: str
    permissions_version: int
    permissions: list[str]


class EffectivePermissionExplanationRead(PermissionRead):
    mode_allowed: bool
    role_allowed: bool
    user_override: Literal["inherit", "allow", "deny"]
    context_allowed: bool
    effective_allowed: bool
    reason: Literal["allowed", "mode_denied", "user_denied", "role_denied"]


class EffectivePermissionExplanationResponse(BaseModel):
    connection_mode: str
    role: RoleSummary
    user: dict | None = None
    permissions: list[EffectivePermissionExplanationRead]
