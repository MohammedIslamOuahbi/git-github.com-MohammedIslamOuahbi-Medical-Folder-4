from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.dependencies.auth import get_current_user
from app.exceptions import ForbiddenException
from app.models.user import User
from app.services.permission_service import permission_service

LEGACY_RESPONSE_ALIASES: dict[str, set[str]] = {
    "workspaces.manage": {"workspaces:manage"},
    "workspaces.view": {"workspaces:view"},
    "medical_campaigns.view": {"campaigns:view"},
    "medical_campaigns.create": {"campaigns:manage"},
    "medical_campaigns.update": {"campaigns:manage"},
    "medical_campaigns.delete": {"campaigns:manage"},
    "medical_campaigns.close": {"campaigns:lock"},
    "medical_campaigns.reopen": {"campaigns:lock"},
}


def get_effective_permissions(user: User) -> list[str]:
    permissions = set(permission_service.get_effective_permission_codes(user))
    for permission_code in list(permissions):
        permissions.update(LEGACY_RESPONSE_ALIASES.get(permission_code, set()))
    return sorted(permissions)


def user_has_permission(user: User, permission_code: str) -> bool:
    effective_permissions = set(get_effective_permissions(user))
    normalized_permission = permission_code.replace(":", ".")
    legacy_permission = normalized_permission.replace(".", ":")
    return (
        permission_code in effective_permissions
        or normalized_permission in effective_permissions
        or legacy_permission in effective_permissions
    )


def has_role(user: User, *roles: str) -> bool:
    normalized_role = (user.role or "").strip().lower()
    return normalized_role in {role.strip().lower() for role in roles}


def require_permission(permission_code: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(current_user, permission_code):
            raise ForbiddenException("Insufficient permissions")
        return current_user

    return dependency
