from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.security import decode_token
from app.dependencies.database import get_db
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.runtime_config import RuntimeConfig
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.mission_service import mission_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class RestoreAuthorization:
    user_id: int
    email: str
    role: str


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError) as exc:
        raise UnauthorizedException("Invalid authentication token") from exc
    user = UserRepository().get(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")
    db.info["sync_source_user_uuid"] = getattr(user, "uuid", None)
    if request is not None:
        mission_credential = request.headers.get("X-Mission-Device-Credential")
        device_uuid = request.headers.get("X-Device-UUID")
        if mission_credential:
            device_payload = mission_service.decode_device_credential(mission_credential)
            db.info["sync_source_device_uuid"] = device_payload.get("device_uuid")
            db.info["sync_mission_session_uuid"] = device_payload.get("mission_uuid")
        elif device_uuid:
            db.info["sync_source_device_uuid"] = device_uuid
    return user


def get_optional_current_user(request: Request, token: str | None = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)) -> User | None:
    if not token:
        return None

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None

    user = UserRepository().get(db, user_id)
    if not user or not user.is_active:
        return None
    db.info["sync_source_user_uuid"] = getattr(user, "uuid", None)
    if request is not None:
        mission_credential = request.headers.get("X-Mission-Device-Credential")
        if mission_credential:
            device_payload = mission_service.decode_device_credential(mission_credential)
            db.info["sync_source_device_uuid"] = device_payload.get("device_uuid")
            db.info["sync_mission_session_uuid"] = device_payload.get("mission_uuid")
    return user


def require_roles(*roles: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        normalized_role = (current_user.role or "").strip().lower()
        if normalized_role not in {role.strip().lower() for role in roles}:
            raise UnauthorizedException("Insufficient role")
        return current_user

    return dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    return require_roles("super_admin", "admin")(current_user)


def require_doctor(current_user: User = Depends(get_current_user)) -> User:
    return require_roles("super_admin", "admin", "doctor")(current_user)


def require_assistant(current_user: User = Depends(get_current_user)) -> User:
    return require_roles("super_admin", "admin", "assistant")(current_user)


def get_restore_authorization(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> RestoreAuthorization:
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError) as exc:
        raise UnauthorizedException("Invalid authentication token") from exc

    user = UserRepository().get(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")
    normalized_role = (user.role or "").strip().lower()
    if normalized_role not in {"super_admin", "admin"}:
        raise ForbiddenException("Vous n'etes pas autorise a effectuer cette operation.")
    return RestoreAuthorization(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )
