from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, object_session

from app.core.audit import create_audit_log
from app.core.enums import ConnectionMode, RoleEnum
from app.core.permission_registry import (
    MINIMUM_LAST_SUPER_ADMIN_PERMISSION_CODES,
    PERMISSION_CATALOGUE,
    PERMISSION_CODES,
    PERMISSION_LOOKUP,
    ROLE_DEFAULT_PERMISSION_CODES,
    SENSITIVE_PERMISSION_CODES,
    SYSTEM_ROLE_DEFINITIONS,
)
from app.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission import UserPermission
from app.schemas.permission import (
    EffectivePermissionExplanationRead,
    EffectivePermissionExplanationResponse,
    EffectivePermissionRead,
    MyPermissionsRead,
    PermissionRead,
    RolePermissionMatrix,
    RolePermissionUpdateRequest,
    RoleSummary,
    UserPermissionCopyRequest,
    UserPermissionMatrix,
    UserPermissionUpdateRequest,
)
from app.services.connection_mode_policy import connection_mode_policy, mode_allows_permission
from app.utils.json_serializer import make_json_serializable


class PermissionService:
    def ensure_seed_data(self, db: Session, *, sync_role_defaults: bool = False) -> None:
        permissions_by_code = {
            permission.code: permission
            for permission in db.scalars(select(Permission)).all()
        }
        for definition in PERMISSION_CATALOGUE:
            permission = permissions_by_code.get(definition.code)
            if permission is None:
                permission = Permission(
                    module=definition.module,
                    action=definition.action,
                    code=definition.code,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category,
                    is_sensitive=definition.is_sensitive,
                    is_system=True,
                    sort_order=definition.sort_order,
                )
                db.add(permission)
                permissions_by_code[definition.code] = permission
                continue

            permission.module = definition.module
            permission.action = definition.action
            permission.name = definition.name
            permission.description = definition.description
            permission.category = definition.category
            permission.is_sensitive = definition.is_sensitive
            permission.is_system = True
            permission.sort_order = definition.sort_order

        db.flush()

        roles_by_code = {
            role.code: role
            for role in db.scalars(select(Role)).all()
        }
        for code, definition in SYSTEM_ROLE_DEFINITIONS.items():
            role = roles_by_code.get(code)
            if role is None:
                role = Role(
                    code=code,
                    name=definition["name"],
                    description=definition["description"],
                    is_system=True,
                    is_active=True,
                )
                db.add(role)
                roles_by_code[code] = role
                continue

            role.name = definition["name"]
            role.description = definition["description"]
            role.is_system = True
            role.is_active = True

        db.flush()

        assigned_permissions = {
            (role_permission.role_id, role_permission.permission_id)
            for role_permission in db.scalars(select(RolePermission)).all()
        }
        for role_code, permission_codes in ROLE_DEFAULT_PERMISSION_CODES.items():
            role = roles_by_code[role_code]
            current_permission_ids = {
                permissions_by_code[code].id
                for code in permission_codes
                if code in permissions_by_code
            }
            existing_rows = db.scalars(select(RolePermission).where(RolePermission.role_id == role.id)).all()
            existing_permission_ids = {row.permission_id for row in existing_rows}
            if sync_role_defaults:
                for row in existing_rows:
                    if row.permission_id not in current_permission_ids:
                        db.delete(row)
            for permission_id in current_permission_ids - existing_permission_ids:
                db.add(RolePermission(role_id=role.id, permission_id=permission_id))
                assigned_permissions.add((role.id, permission_id))

        db.flush()

        users_without_role_id = db.scalars(select(User).where(User.role_id.is_(None))).all()
        for user in users_without_role_id:
            normalized_role = self.normalize_role_code(user.role)
            role = roles_by_code.get(normalized_role)
            if role is not None:
                user.role_id = role.id
                user.role = normalized_role

    def normalize_role_code(self, role_code: str | None) -> str:
        normalized = (role_code or RoleEnum.assistant.value).strip().lower().replace(" ", "_")
        if normalized not in SYSTEM_ROLE_DEFINITIONS:
            return RoleEnum.assistant.value
        return normalized

    def list_permissions(self, db: Session) -> list[PermissionRead]:
        permissions = db.scalars(
            select(Permission)
            .where(Permission.code.in_(PERMISSION_CODES))
            .order_by(Permission.sort_order.asc(), Permission.code.asc())
        ).all()
        result: list[PermissionRead] = []
        for permission in permissions:
            definition = PERMISSION_LOOKUP.get(permission.code)
            if definition is None:
                continue
            result.append(
                PermissionRead(
                    id=permission.id,
                    code=permission.code,
                    module=permission.module or definition.module,
                    action=permission.action or definition.action,
                    name=permission.name or definition.name,
                    description=permission.description or definition.description,
                    category=permission.category or definition.category,
                    is_sensitive=permission.is_sensitive,
                    is_system=permission.is_system,
                    sort_order=permission.sort_order,
                    created_at=permission.created_at,
                    updated_at=permission.updated_at,
                )
            )
        return result

    def list_roles(self, db: Session) -> list[RoleSummary]:
        roles = db.scalars(select(Role).order_by(Role.id.asc())).all()
        return [RoleSummary.model_validate(role) for role in roles]

    def get_role(self, db: Session, role_id: int) -> Role:
        role = db.scalar(select(Role).where(Role.id == role_id))
        if role is None:
            raise NotFoundException("Role not found")
        return role

    def get_role_by_code(self, db: Session, role_code: str) -> Role | None:
        return db.scalar(select(Role).where(Role.code == self.normalize_role_code(role_code)))

    def get_permission_map(self, db: Session) -> dict[str, Permission]:
        return {permission.code: permission for permission in db.scalars(select(Permission)).all()}

    def get_effective_permission_codes(self, user: User) -> list[str]:
        role_permission_codes = self.get_role_permission_codes_for_user(user)
        override_lookup = {
            user_permission.permission.code: user_permission.effect
            for user_permission in user.user_permissions
            if user_permission.permission is not None
        }

        effective_codes: set[str] = set()
        for definition in PERMISSION_CATALOGUE:
            override = override_lookup.get(definition.code)
            if override == "allow":
                effective_codes.add(definition.code)
            elif override == "deny":
                effective_codes.discard(definition.code)
            elif definition.code in role_permission_codes:
                effective_codes.add(definition.code)

        return sorted(effective_codes)

    def get_role_permission_codes_for_user(self, user: User) -> set[str]:
        if user.assigned_role is not None and user.assigned_role.role_permissions:
            return {
                role_permission.permission.code
                for role_permission in user.assigned_role.role_permissions
                if role_permission.permission is not None
            }

        role_code = self.normalize_role_code(user.role)
        return set(ROLE_DEFAULT_PERMISSION_CODES.get(role_code, set()))

    def build_effective_permissions(
        self,
        user: User,
        actor: User | None = None,
        permissions_by_code: dict[str, Permission] | None = None,
    ) -> list[EffectivePermissionRead]:
        role_permission_codes = self.get_role_permission_codes_for_user(user)
        override_lookup = {
            user_permission.permission.code: user_permission.effect
            for user_permission in user.user_permissions
            if user_permission.permission is not None
        }
        actor_codes = set(self.get_effective_permission_codes(actor)) if actor is not None else set()
        is_last_super_admin = self.is_last_active_super_admin(user)
        result: list[EffectivePermissionRead] = []
        permission_lookup_by_code = permissions_by_code or {permission.code: permission for permission in self.iter_known_permissions(user)}

        for definition in PERMISSION_CATALOGUE:
            permission = permission_lookup_by_code.get(definition.code)
            if permission is None:
                continue
            override = override_lookup.get(definition.code)
            role_allowed = definition.code in role_permission_codes
            if override == "allow":
                effective_allowed = True
                source = "user_allow"
            elif override == "deny":
                effective_allowed = False
                source = "user_deny"
            elif role_allowed:
                effective_allowed = True
                source = "role"
            else:
                effective_allowed = False
                source = "default_deny"

            can_manage = actor is None or definition.code in actor_codes
            if definition.code in SENSITIVE_PERMISSION_CODES and actor is not None:
                can_manage = can_manage and "users.grant_sensitive_permissions" in actor_codes
            if is_last_super_admin and definition.code in MINIMUM_LAST_SUPER_ADMIN_PERMISSION_CODES:
                can_manage = False

            result.append(
                EffectivePermissionRead(
                    id=permission.id,
                    code=permission.code,
                    module=permission.module,
                    action=permission.action,
                    name=permission.name,
                    description=permission.description,
                    category=permission.category,
                    is_sensitive=permission.is_sensitive,
                    role_allowed=role_allowed,
                    override=override,
                    effective_allowed=effective_allowed,
                    source=source,
                    can_manage=can_manage,
                )
            )
        return result

    def iter_known_permissions(self, user: User) -> Iterable[Permission]:
        seen: dict[str, Permission] = {}
        if user.assigned_role is not None:
            for role_permission in user.assigned_role.role_permissions:
                if role_permission.permission is not None:
                    seen[role_permission.permission.code] = role_permission.permission
        for user_permission in user.user_permissions:
            if user_permission.permission is not None:
                seen[user_permission.permission.code] = user_permission.permission
        return seen.values()

    def is_last_active_super_admin(self, user: User) -> bool:
        return self.normalize_role_code(user.role) == RoleEnum.super_admin.value and user.is_active and getattr(
            user, "_last_active_super_admin_count", None
        ) == 1

    def attach_last_super_admin_flag(self, db: Session, *users: User) -> None:
        count = db.scalar(
            select(func.count(User.id)).where(
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                func.lower(User.role) == RoleEnum.super_admin.value,
            )
        ) or 0
        for user in users:
            setattr(user, "_last_active_super_admin_count", count)

    def ensure_permission_grantable(self, actor: User, permission_code: str) -> None:
        actor_codes = set(self.get_effective_permission_codes(actor))
        if permission_code not in actor_codes:
            raise ForbiddenException(f"You cannot manage permission '{permission_code}'.")
        if permission_code in SENSITIVE_PERMISSION_CODES and "users.grant_sensitive_permissions" not in actor_codes:
            raise ForbiddenException("Granting sensitive permissions requires users.grant_sensitive_permissions.")

    def require_permission(self, user: User, permission_code: str, *, worker_id: int | None = None) -> None:
        if permission_code not in set(self.get_effective_permission_codes(user)):
            raise ForbiddenException("Insufficient permissions")
        connection_mode_policy.ensure_allowed(object_session(user), user, permission_code, worker_id=worker_id)

    def require_any_permission(self, user: User, *permission_codes: str, worker_id: int | None = None) -> None:
        user_permissions = set(self.get_effective_permission_codes(user))
        allowed_codes = [permission_code for permission_code in permission_codes if permission_code in user_permissions]
        if not allowed_codes:
            raise ForbiddenException("Insufficient permissions")
        db = object_session(user)
        for permission_code in allowed_codes:
            try:
                connection_mode_policy.ensure_allowed(db, user, permission_code, worker_id=worker_id)
                return
            except ForbiddenException:
                continue
        raise ForbiddenException("This operation is not available in the current connection mode.")

    def require_all_permissions(self, user: User, *permission_codes: str, worker_id: int | None = None) -> None:
        user_permissions = set(self.get_effective_permission_codes(user))
        missing = [permission_code for permission_code in permission_codes if permission_code not in user_permissions]
        if missing:
            raise ForbiddenException("Insufficient permissions", {"missing_permissions": missing})
        db = object_session(user)
        for permission_code in permission_codes:
            connection_mode_policy.ensure_allowed(db, user, permission_code, worker_id=worker_id)

    def get_role_permissions(self, db: Session, role_id: int) -> RolePermissionMatrix:
        role = db.scalar(
            select(Role)
            .where(Role.id == role_id)
            .options(joinedload(Role.role_permissions).joinedload(RolePermission.permission))
        )
        if role is None:
            raise NotFoundException("Role not found")
        return RolePermissionMatrix(
            role=RoleSummary.model_validate(role),
            permissions=self.list_permissions(db),
            assigned_permission_codes=sorted(
                row.permission.code for row in role.role_permissions if row.permission is not None
            ),
        )

    def update_role_permissions(
        self,
        db: Session,
        role_id: int,
        payload: RolePermissionUpdateRequest,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RolePermissionMatrix:
        self.require_permission(actor, "roles.manage_permissions")
        role = self.get_role(db, role_id)
        requested_codes = set(payload.permission_codes)
        invalid_codes = sorted(code for code in requested_codes if code not in PERMISSION_CODES)
        if invalid_codes:
            raise BadRequestException("Invalid permission codes supplied.", {"permission_codes": invalid_codes})
        for code in requested_codes:
            self.ensure_permission_grantable(actor, code)

        permissions_by_code = self.get_permission_map(db)
        existing_rows = db.scalars(select(RolePermission).where(RolePermission.role_id == role.id)).all()
        existing_by_code = {
            row.permission.code: row
            for row in existing_rows
            if row.permission is not None
        }
        previous_codes = set(existing_by_code)
        for code, row in existing_by_code.items():
            if code not in requested_codes:
                db.delete(row)
        for code in requested_codes - previous_codes:
            db.add(RolePermission(role_id=role.id, permission_id=permissions_by_code[code].id))

        db.flush()
        create_audit_log(
            db,
            user_id=actor.id,
            actor_user_id=actor.id,
            action="role.permissions.updated",
            entity_type="role",
            entity_id=role.id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"permission_codes": sorted(previous_codes)},
            new_values={"permission_codes": sorted(requested_codes)},
        )
        db.commit()
        return self.get_role_permissions(db, role_id)

    def get_user_with_permissions(self, db: Session, user_id: int) -> User:
        user = db.scalar(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(
                joinedload(User.assigned_role).joinedload(Role.role_permissions).joinedload(RolePermission.permission),
                joinedload(User.user_permissions).joinedload(UserPermission.permission),
            )
        )
        if user is None:
            raise NotFoundException("User not found")
        self.attach_last_super_admin_flag(db, user)
        return user

    def get_user_permission_matrix(self, db: Session, user_id: int, actor: User) -> UserPermissionMatrix:
        self.require_permission(actor, "users.view_permissions")
        user = self.get_user_with_permissions(db, user_id)
        permissions = self.build_effective_permissions(user, actor, self.get_permission_map(db))
        return UserPermissionMatrix(
            user={
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "username": None,
                "email": user.email,
                "role": self.normalize_role_code(user.role),
                "isActive": user.is_active,
            },
            permissions_version=user.permissions_version,
            direct_override_count=len(user.user_permissions),
            effective_permission_count=sum(1 for permission in permissions if permission.effective_allowed),
            is_last_active_super_admin=self.is_last_active_super_admin(user),
            permissions=permissions,
        )

    def update_user_permissions(
        self,
        db: Session,
        user_id: int,
        payload: UserPermissionUpdateRequest,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserPermissionMatrix:
        user = self.get_user_with_permissions(db, user_id)
        self._ensure_actor_can_edit_user_permissions(actor, user)
        requested_codes = [item.permission_code for item in payload.permissions]
        invalid_codes = sorted(code for code in requested_codes if code not in PERMISSION_CODES)
        if invalid_codes:
            raise BadRequestException("Invalid permission codes supplied.", {"permission_codes": invalid_codes})

        permissions_by_code = self.get_permission_map(db)
        existing_by_code = {
            row.permission.code: row
            for row in user.user_permissions
            if row.permission is not None
        }
        old_values = {
            "overrides": {
                code: row.effect
                for code, row in existing_by_code.items()
            }
        }
        for item in payload.permissions:
            self.ensure_permission_grantable(actor, item.permission_code)
            if self.is_last_active_super_admin(user) and item.permission_code in MINIMUM_LAST_SUPER_ADMIN_PERMISSION_CODES and item.state == "deny":
                raise ConflictException("Minimum recovery permissions cannot be denied for the last active Super Admin.")

            existing = existing_by_code.get(item.permission_code)
            if item.state == "inherit":
                if existing is not None:
                    db.delete(existing)
                continue

            if existing is None:
                existing = UserPermission(
                    user_id=user.id,
                    permission_id=permissions_by_code[item.permission_code].id,
                    effect=item.state,
                    granted_by_user_id=actor.id,
                    reason=payload.reason,
                )
                db.add(existing)
                existing_by_code[item.permission_code] = existing
                continue

            existing.effect = item.state
            existing.granted_by_user_id = actor.id
            existing.reason = payload.reason
            existing.updated_at = datetime.now(timezone.utc)

        self._touch_permissions(user)
        db.flush()
        db.refresh(user)
        self.attach_last_super_admin_flag(db, user)
        create_audit_log(
            db,
            user_id=actor.id,
            actor_user_id=actor.id,
            action="user.permissions.updated",
            entity_type="user",
            entity_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values,
            new_values={
                "overrides": {
                    row.permission.code: row.effect
                    for row in user.user_permissions
                    if row.permission is not None
                },
                "reason": payload.reason,
            },
            metadata={"sensitive_permissions": [item.permission_code for item in payload.permissions if item.permission_code in SENSITIVE_PERMISSION_CODES]},
        )
        db.commit()
        return self.get_user_permission_matrix(db, user.id, actor)

    def reset_user_permissions(
        self,
        db: Session,
        user_id: int,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserPermissionMatrix:
        user = self.get_user_with_permissions(db, user_id)
        self._ensure_actor_can_edit_user_permissions(actor, user)
        previous_overrides = {
            row.permission.code: row.effect
            for row in user.user_permissions
            if row.permission is not None
        }
        if self.is_last_active_super_admin(user):
            remaining = set(self.get_effective_permission_codes(user))
            if not MINIMUM_LAST_SUPER_ADMIN_PERMISSION_CODES.issubset(remaining):
                raise ConflictException("The last active Super Admin must retain minimum recovery permissions.")
        for override in db.scalars(select(UserPermission).where(UserPermission.user_id == user.id)).all():
            db.delete(override)
        self._touch_permissions(user)
        db.flush()
        create_audit_log(
            db,
            user_id=actor.id,
            actor_user_id=actor.id,
            action="user.permissions.reset",
            entity_type="user",
            entity_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"overrides": previous_overrides},
            new_values={"overrides": {}},
        )
        db.commit()
        return self.get_user_permission_matrix(db, user.id, actor)

    def copy_user_permissions(
        self,
        db: Session,
        target_user_id: int,
        payload: UserPermissionCopyRequest,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserPermissionMatrix:
        self.require_permission(actor, "users.copy_permissions")
        source_user = self.get_user_with_permissions(db, payload.source_user_id)
        target_user = self.get_user_with_permissions(db, target_user_id)
        self._ensure_actor_can_edit_user_permissions(actor, target_user)
        if source_user.id == target_user.id:
            raise BadRequestException("Source and target users must be different.")
        if payload.copy_role:
            next_role = self.normalize_role_code(source_user.role)
            if next_role == RoleEnum.super_admin.value:
                raise ForbiddenException("Copying a Super Admin role is not allowed through this endpoint.")
            self.ensure_permission_grantable(actor, "users.assign_role")
            target_role = self.get_role_by_code(db, next_role)
            if target_role is None:
                raise NotFoundException("Source role not found.")
            target_user.role = next_role
            target_user.role_id = target_role.id

        if payload.copy_overrides:
            for override in db.scalars(select(UserPermission).where(UserPermission.user_id == target_user.id)).all():
                db.delete(override)
            permissions_by_code = self.get_permission_map(db)
            for source_override in source_user.user_permissions:
                if source_override.permission is None:
                    continue
                self.ensure_permission_grantable(actor, source_override.permission.code)
                db.add(
                    UserPermission(
                        user_id=target_user.id,
                        permission_id=permissions_by_code[source_override.permission.code].id,
                        effect=source_override.effect,
                        granted_by_user_id=actor.id,
                        reason=payload.reason,
                    )
                )

        self._touch_permissions(target_user)
        db.flush()
        create_audit_log(
            db,
            user_id=actor.id,
            actor_user_id=actor.id,
            action="user.permissions.copied",
            entity_type="user",
            entity_id=target_user.id,
            target_user_id=target_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "source_user_id": source_user.id,
                "copy_role": payload.copy_role,
                "copy_overrides": payload.copy_overrides,
                "reason": payload.reason,
            },
        )
        db.commit()
        return self.get_user_permission_matrix(db, target_user.id, actor)

    def get_my_permissions(self, db: Session, user: User) -> MyPermissionsRead:
        current_user = self.get_user_with_permissions(db, user.id)
        return MyPermissionsRead(
            role=self.normalize_role_code(current_user.role),
            permissions_version=current_user.permissions_version,
            permissions=self.get_effective_permission_codes(current_user),
        )

    def explain_effective_permissions(
        self,
        db: Session,
        *,
        actor: User,
        connection_mode: ConnectionMode,
        role_id: int | None = None,
        user_id: int | None = None,
    ) -> EffectivePermissionExplanationResponse:
        target_user = self.get_user_with_permissions(db, user_id) if user_id is not None else None
        if role_id is not None:
            role = self.get_role(db, role_id)
        elif target_user is not None and target_user.assigned_role is not None:
            role = target_user.assigned_role
        else:
            role = self.get_user_with_permissions(db, actor.id).assigned_role

        if role is None:
            raise NotFoundException("Role not found")

        role_codes = {
            row.permission.code
            for row in role.role_permissions
            if row.permission is not None
        }
        overrides = {
            row.permission.code: row.effect
            for row in (target_user.user_permissions if target_user is not None else [])
            if row.permission is not None
        }
        permissions = []
        for permission in self.list_permissions(db):
            mode_allowed = mode_allows_permission(connection_mode, permission.code)
            role_allowed = permission.code in role_codes
            override = overrides.get(permission.code, "inherit")
            before_mode = override == "allow" or (override == "inherit" and role_allowed)
            effective_allowed = mode_allowed and before_mode
            reason = (
                "mode_denied"
                if not mode_allowed
                else "user_denied"
                if override == "deny"
                else "allowed"
                if effective_allowed
                else "role_denied"
            )
            permissions.append(
                EffectivePermissionExplanationRead(
                    **permission.model_dump(),
                    mode_allowed=mode_allowed,
                    role_allowed=role_allowed,
                    user_override=override,
                    context_allowed=True,
                    effective_allowed=effective_allowed,
                    reason=reason,
                )
            )

        return EffectivePermissionExplanationResponse(
            connection_mode=connection_mode.value,
            role=RoleSummary.model_validate(role),
            user=(
                {
                    "id": target_user.id,
                    "name": f"{target_user.first_name} {target_user.last_name}".strip(),
                    "role": self.normalize_role_code(target_user.role),
                }
                if target_user is not None
                else None
            ),
            permissions=permissions,
        )

    def _ensure_actor_can_edit_user_permissions(self, actor: User, target: User) -> None:
        self.require_permission(actor, "users.view_permissions")
        if actor.id == target.id:
            raise ForbiddenException("Users cannot modify their own permissions.")
        if self.normalize_role_code(target.role) == RoleEnum.super_admin.value:
            self.require_permission(actor, "users.edit_super_admin_permissions")
        else:
            self.require_permission(actor, "users.edit_permissions")

    def _touch_permissions(self, user: User) -> None:
        user.permissions_version += 1
        user.last_permissions_update_at = datetime.now(timezone.utc)


permission_service = PermissionService()
