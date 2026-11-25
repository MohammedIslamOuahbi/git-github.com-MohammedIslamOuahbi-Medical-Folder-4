from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.exceptions import BadRequestException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenPair
from app.services.permission_service import permission_service


class AuthService:
    def __init__(self) -> None:
        self.user_repository = UserRepository()

    def login(self, db: Session, payload: LoginRequest) -> tuple[TokenPair, User]:
        user = self.user_repository.get_by_email(db, payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("Inactive user")
        # Login is deliberately read-only while guarded syncable writes remain
        # suspended. Last-login auditing must be handled by a reviewed write
        # contract; authentication must not mutate the user row.
        return self._build_tokens(user), user

    def me(self, current_user: User) -> User:
        return current_user

    def refresh(self, db: Session, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except Exception as exc:
            raise UnauthorizedException("Invalid refresh token") from exc
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid refresh token type")
        user = self.user_repository.get(db, int(payload["sub"]))
        if not user:
            raise UnauthorizedException("User not found")
        return self._build_tokens(user)

    def logout(self) -> dict:
        return {"logged_out": True}

    def create_platform_user(
        self,
        db: Session,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        role: str = "admin",
    ) -> User:
        existing = self.user_repository.get_by_email(db, email)
        if existing:
            return existing
        permission_service.ensure_seed_data(db)
        role_code = permission_service.normalize_role_code(role)
        role = permission_service.get_role_by_code(db, role_code)
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            role=role_code,
            role_id=role.id if role is not None else None,
            is_active=True,
        )
        return self.user_repository.create(db, user)

    def create_admin_user(self, db: Session, first_name: str, last_name: str, email: str, password: str) -> User:
        return self.create_platform_user(db, first_name, last_name, email, password, role="admin")

    def _build_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(str(user.id), user.role, user.permissions_version),
            refresh_token=create_refresh_token(str(user.id), user.role, user.permissions_version),
        )
