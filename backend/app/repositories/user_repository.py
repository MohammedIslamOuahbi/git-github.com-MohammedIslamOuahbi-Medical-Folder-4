from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission
from app.models.user import User
from app.schemas.pagination import PaginationParams
from app.utils.filters import build_search_filter


class UserRepository:
    searchable_fields = ["first_name", "last_name", "email", "role", "qualification"]

    def list(self, db: Session, params: PaginationParams, role: str | None = None) -> tuple[list[User], int]:
        query = select(User).where(User.deleted_at.is_(None)).options(
            joinedload(User.user_permissions).joinedload(UserPermission.permission),
            joinedload(User.assigned_role).joinedload(Role.role_permissions).joinedload(RolePermission.permission),
        )
        count_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
        if role:
            normalized_role = role.lower()
            query = query.where(func.lower(User.role) == normalized_role)
            count_query = count_query.where(func.lower(User.role) == normalized_role)
        if params.search:
            search_filter = build_search_filter(User, params.search, self.searchable_fields)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(User, params.sort_by or "id", User.id)
        query = query.order_by(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())
        items = db.scalars(query.offset(params.offset).limit(params.limit)).unique().all()
        total = db.scalar(count_query) or 0
        return items, total

    def get(self, db: Session, user_id: int) -> User | None:
        query = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(
                joinedload(User.user_permissions).joinedload(UserPermission.permission),
                joinedload(User.assigned_role).joinedload(Role.role_permissions).joinedload(RolePermission.permission),
            )
        )
        return db.scalar(query)

    def get_by_email(self, db: Session, email: str) -> User | None:
        normalized_email = email.strip().lower()
        query = (
            select(User)
            .where(func.lower(User.email) == normalized_email, User.deleted_at.is_(None))
            .options(
                joinedload(User.user_permissions).joinedload(UserPermission.permission),
                joinedload(User.assigned_role).joinedload(Role.role_permissions).joinedload(RolePermission.permission),
            )
        )
        return db.scalar(query)

    def create(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def update(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
