from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.permission_service import permission_service


def require_permission(permission_code: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        permission_service.require_permission(current_user, permission_code)
        return current_user

    return dependency


def require_any_permission(*permission_codes: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        permission_service.require_any_permission(current_user, *permission_codes)
        return current_user

    return dependency


def require_all_permissions(*permission_codes: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        permission_service.require_all_permissions(current_user, *permission_codes)
        return current_user

    return dependency


__all__ = ["require_permission", "require_any_permission", "require_all_permissions"]
