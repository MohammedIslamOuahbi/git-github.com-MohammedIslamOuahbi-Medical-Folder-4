"""add hybrid permission system

Revision ID: 20260727_01
Revises: 20260723_01
Create Date: 2026-07-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260727_01"
down_revision = "20260723_01"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "roles"):
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, unique=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("sync_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("origin_device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("last_modified_device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("origin_mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("last_modified_mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("central_version", sa.Integer(), nullable=True),
            sa.Column("central_sync_status", sa.String(length=30), nullable=False, server_default=sa.text("'never_submitted'")),
            sa.Column("central_sequence", sa.BigInteger(), nullable=True),
            sa.Column("central_finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("central_server_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.UniqueConstraint("code", name="uq_roles_code"),
        )
        op.create_index("ix_roles_code", "roles", ["code"], unique=False)
        op.create_index("ix_roles_is_active", "roles", ["is_active"], unique=False)

    inspector = inspect(bind)
    permission_columns = _column_names(inspector, "permissions")
    if "module" not in permission_columns:
        op.add_column("permissions", sa.Column("module", sa.String(length=100), nullable=True))
    if "action" not in permission_columns:
        op.add_column("permissions", sa.Column("action", sa.String(length=100), nullable=True))
    if "description" not in permission_columns:
        op.add_column("permissions", sa.Column("description", sa.Text(), nullable=True))
    if "category" not in permission_columns:
        op.add_column("permissions", sa.Column("category", sa.String(length=100), nullable=True))
    if "is_sensitive" not in permission_columns:
        op.add_column("permissions", sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if "is_system" not in permission_columns:
        op.add_column("permissions", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    if "sort_order" not in permission_columns:
        op.add_column("permissions", sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")))
    if "created_at" not in permission_columns:
        op.add_column("permissions", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    if "updated_at" not in permission_columns:
        op.add_column("permissions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    inspector = inspect(bind)
    user_columns = _column_names(inspector, "users")
    if "role_id" not in user_columns:
        op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
    if "permissions_version" not in user_columns:
        op.add_column("users", sa.Column("permissions_version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    if "last_permissions_update_at" not in user_columns:
        op.add_column("users", sa.Column("last_permissions_update_at", sa.DateTime(timezone=True), nullable=True))

    inspector = inspect(bind)
    user_permission_columns = _column_names(inspector, "user_permissions")
    if "effect" not in user_permission_columns:
        op.add_column("user_permissions", sa.Column("effect", sa.String(length=20), nullable=False, server_default=sa.text("'allow'")))
    if "granted_by_user_id" not in user_permission_columns:
        op.add_column("user_permissions", sa.Column("granted_by_user_id", sa.Integer(), nullable=True))
    if "reason" not in user_permission_columns:
        op.add_column("user_permissions", sa.Column("reason", sa.String(length=500), nullable=True))
    if "created_at" not in user_permission_columns:
        op.add_column("user_permissions", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    if "updated_at" not in user_permission_columns:
        op.add_column("user_permissions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    inspector = inspect(bind)
    audit_columns = _column_names(inspector, "audit_logs")
    if "actor_user_id" not in audit_columns:
        op.add_column("audit_logs", sa.Column("actor_user_id", sa.Integer(), nullable=True))
    if "target_user_id" not in audit_columns:
        op.add_column("audit_logs", sa.Column("target_user_id", sa.Integer(), nullable=True))
    if "user_agent" not in audit_columns:
        op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=500), nullable=True))
    if "old_values" not in audit_columns:
        op.add_column("audit_logs", sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "new_values" not in audit_columns:
        op.add_column("audit_logs", sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "metadata" not in audit_columns:
        op.add_column("audit_logs", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    inspector = inspect(bind)
    if not _table_exists(inspector, "role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
        )
        op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"], unique=False)
        op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"], unique=False)

    inspector = inspect(bind)
    if "uq_permissions_module_action" not in {constraint["name"] for constraint in inspector.get_unique_constraints("permissions")}:
        op.create_unique_constraint("uq_permissions_module_action", "permissions", ["module", "action"])
    if "uq_user_permissions_user_permission" not in {constraint["name"] for constraint in inspector.get_unique_constraints("user_permissions")}:
        op.create_unique_constraint("uq_user_permissions_user_permission", "user_permissions", ["user_id", "permission_id"])

    index_names = _index_names(inspector, "permissions")
    if "ix_permissions_module" not in index_names:
        op.create_index("ix_permissions_module", "permissions", ["module"], unique=False)
    if "ix_permissions_action" not in index_names:
        op.create_index("ix_permissions_action", "permissions", ["action"], unique=False)
    if "ix_permissions_category" not in index_names:
        op.create_index("ix_permissions_category", "permissions", ["category"], unique=False)
    if "ix_permissions_is_sensitive" not in index_names:
        op.create_index("ix_permissions_is_sensitive", "permissions", ["is_sensitive"], unique=False)

    index_names = _index_names(inspector, "users")
    if "ix_users_role_id" not in index_names:
        op.create_index("ix_users_role_id", "users", ["role_id"], unique=False)
    if "ix_users_is_active" not in index_names:
        op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)

    index_names = _index_names(inspector, "audit_logs")
    if "ix_audit_logs_actor_user_id" not in index_names:
        op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    if "ix_audit_logs_target_user_id" not in index_names:
        op.create_index("ix_audit_logs_target_user_id", "audit_logs", ["target_user_id"], unique=False)

    op.execute(
        """
        UPDATE user_permissions
        SET effect = 'allow'
        WHERE effect IS NULL
        """
    )

    from app.services.permission_service import permission_service

    session = sa.orm.Session(bind=bind)
    try:
        # Migration-only reference seed.  This flag is set on this local
        # Alembic session only; it is never accepted from HTTP or runtime code.
        session.info["sync_bootstrap_mode"] = True
        permission_service.ensure_seed_data(session, sync_role_defaults=True)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for index_name, table_name in [
        ("ix_audit_logs_target_user_id", "audit_logs"),
        ("ix_audit_logs_actor_user_id", "audit_logs"),
        ("ix_users_is_active", "users"),
        ("ix_users_role_id", "users"),
        ("ix_permissions_is_sensitive", "permissions"),
        ("ix_permissions_category", "permissions"),
        ("ix_permissions_action", "permissions"),
        ("ix_permissions_module", "permissions"),
        ("ix_role_permissions_permission_id", "role_permissions"),
        ("ix_role_permissions_role_id", "role_permissions"),
        ("ix_roles_is_active", "roles"),
        ("ix_roles_code", "roles"),
    ]:
        if _table_exists(inspector, table_name) and index_name in _index_names(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)

    if _table_exists(inspector, "role_permissions"):
        op.drop_table("role_permissions")
    if _table_exists(inspector, "roles"):
        op.drop_table("roles")
