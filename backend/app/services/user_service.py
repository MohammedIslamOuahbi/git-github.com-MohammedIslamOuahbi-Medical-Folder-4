from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.permissions import has_role
from app.core.security import verify_password
from app.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserCreate, UserUpdate
from app.services.permission_service import permission_service
from app.services.user_signature_service import UserSignatureService
from app.utils.pagination import build_paginated_response
from app.utils.password import hash_password


class UserService:
    def __init__(self) -> None:
        self.repository = UserRepository()
        self.signature_service = UserSignatureService()

    def list(self, db: Session, params: PaginationParams, role: str | None = None):
        items, total = self.repository.list(db, params, role=role)
        return build_paginated_response(items, total, params)

    def get(self, db: Session, user_id: int) -> User:
        user = self.repository.get(db, user_id)
        if not user:
            raise NotFoundException("User not found")
        return user

    def _ensure_role_can_manage_target(self, actor: User, target_role: str) -> None:
        if has_role(actor, "super_admin"):
            return
        if target_role in {"super_admin", "admin"}:
            raise BadRequestException("Only super admins can manage admin accounts")

    def create(self, db: Session, payload: UserCreate, current_user: User, role: str | None = None) -> User:
        permission_service.ensure_seed_data(db)
        if self.repository.get_by_email(db, payload.email):
            raise BadRequestException("Email already exists")
        target_role = permission_service.normalize_role_code(role or payload.role)
        if payload.role_code and permission_service.normalize_role_code(payload.role_code) != target_role:
            raise BadRequestException("role_code does not match role")
        for unsupported in ("signatureImageUrl", "hasSignature", "signatureUploadedAt"):
            if getattr(payload, unsupported, None) not in (None, False):
                raise BadRequestException(f"Unsupported user field: {unsupported}")
        self._ensure_role_can_manage_target(current_user, target_role)
        if target_role == "super_admin":
            permission_service.require_permission(current_user, "users.promote_to_super_admin")
        qualification = payload.qualification.strip() if payload.qualification else None
        if target_role == "doctor" and not qualification:
            raise BadRequestException("Qualification is required for doctors")
        role_record = permission_service.get_role_by_code(db, target_role)
        user = User(
            **payload.model_dump(exclude={"password", "role", "role_code", "qualification", "signatureImageUrl", "hasSignature", "signatureUploadedAt"}),
            role=target_role,
            role_id=role_record.id if role_record is not None else None,
            qualification=qualification if target_role == "doctor" else None,
            password_hash=hash_password(payload.password),
        )
        return self.repository.create(db, user)

    def update(self, db: Session, user_id: int, payload: UserUpdate, current_user: User) -> User:
        user = self.get(db, user_id)
        permission_service.attach_last_super_admin_flag(db, user)
        if user.id == current_user.id and "role" in payload.model_dump(exclude_unset=True):
            raise ForbiddenException("Users cannot change their own role.")
        if user.id == current_user.id and "is_active" in payload.model_dump(exclude_unset=True) and payload.is_active is False:
            raise ForbiddenException("Users cannot deactivate themselves.")
        next_role = permission_service.normalize_role_code(payload.role or user.role)
        self._ensure_role_can_manage_target(current_user, next_role)
        if next_role == "super_admin" and user.role != "super_admin":
            permission_service.require_permission(current_user, "users.promote_to_super_admin")
        if user.role == "super_admin" and next_role != "super_admin":
            if permission_service.is_last_active_super_admin(user):
                raise ConflictException("The last active Super Admin cannot be demoted.")
            permission_service.require_permission(current_user, "users.demote_super_admin")
        incoming_qualification = payload.qualification.strip() if payload.qualification else None
        next_qualification = incoming_qualification if "qualification" in payload.model_dump(exclude_unset=True) else user.qualification
        if next_role == "doctor" and not next_qualification:
            raise BadRequestException("Qualification is required for doctors")
        role_record = permission_service.get_role_by_code(db, next_role)
        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "password" and value:
                user.password_hash = hash_password(value)
            elif key == "role" and value:
                user.role = next_role
                user.role_id = role_record.id if role_record is not None else user.role_id
            elif key == "qualification":
                user.qualification = incoming_qualification if next_role == "doctor" else None
            else:
                setattr(user, key, value)
        if next_role != "doctor":
            user.qualification = None
        if user.role == "super_admin" and user.is_active is False and permission_service.is_last_active_super_admin(user):
            raise ConflictException("The last active Super Admin cannot be deactivated.")
        user.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, user)

    def update_self(self, db: Session, current_user: User, payload: UserUpdate) -> User:
        user = self.get(db, current_user.id)
        allowed_updates = payload.model_dump(
            exclude_unset=True,
            include={"first_name", "last_name", "phone", "password", "signature_png"},
        )
        for key, value in allowed_updates.items():
            if key == "password" and value:
                user.password_hash = hash_password(value)
            elif key == "signature_png":
                raise BadRequestException("Use the PNG signature upload endpoint to manage validator signatures.")
            else:
                setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        return self.repository.update(db, user)

    def delete(self, db: Session, user_id: int, current_user: User, password: str) -> User:
        user = self.get(db, user_id)
        permission_service.attach_last_super_admin_flag(db, user)
        self._ensure_role_can_manage_target(current_user, user.role)
        if user.id == current_user.id:
            raise ForbiddenException("Users cannot delete themselves.")
        if permission_service.is_last_active_super_admin(user):
            raise ConflictException("The last active Super Admin cannot be deleted.")
        if not password:
            raise BadRequestException("Password is required to remove a user.")
        if not verify_password(password, current_user.password_hash):
            raise UnauthorizedException("Invalid password. User was not removed.")
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        return self.repository.update(db, user)
