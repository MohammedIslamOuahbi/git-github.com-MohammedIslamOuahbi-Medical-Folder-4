from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import get_effective_permissions
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, UserMe
from app.schemas.user import UserUpdate
from app.services.auth_service import AuthService
from app.services.permission_service import permission_service
from app.services.user_signature_service import UserSignatureService
from app.services.user_service import UserService
from app.utils.responses import success_response

router = APIRouter(prefix="/auth", tags=["Auth"])
service = AuthService()
user_service = UserService()
signature_service = UserSignatureService()


@router.post("/login", status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    tokens, _ = service.login(db, payload)
    return success_response("Login successful", tokens.model_dump())


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    payload = UserMe.model_validate(current_user).model_dump()
    payload["role_code"] = permission_service.normalize_role_code(current_user.role)
    payload["permissions_version"] = current_user.permissions_version
    payload["permissions"] = get_effective_permissions(current_user)
    payload.update(signature_service.serialize_signature(current_user))
    return success_response("Authenticated user", payload)


@router.put("/me")
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = user_service.update_self(db, current_user, payload)
    response = UserMe.model_validate(user).model_dump()
    response["role_code"] = permission_service.normalize_role_code(user.role)
    response["permissions_version"] = user.permissions_version
    response["permissions"] = get_effective_permissions(user)
    response.update(signature_service.serialize_signature(user))
    return success_response("Profile updated", response)


@router.post("/logout")
def logout():
    return success_response("Logout successful", service.logout())


@router.post("/refresh")
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    tokens = service.refresh(db, payload.refresh_token)
    return success_response("Token refreshed", tokens.model_dump())


@router.get("/me/permissions")
def my_permissions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response("Current user permissions retrieved", permission_service.get_my_permissions(db, current_user))
