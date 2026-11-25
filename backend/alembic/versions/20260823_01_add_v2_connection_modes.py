"""add V2 connection modes and audit context

Revision ID: 20260823_01
Revises: 20260727_01
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260823_01"
down_revision = "20260727_01"
branch_labels = None
depends_on = None


def _columns(inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _constraints(inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name) if constraint.get("name")}


def _has_unique_key(inspector, table_name: str, columns: list[str]) -> bool:
    """PostgreSQL only permits a foreign key to a primary or unique key."""
    if table_name not in inspector.get_table_names():
        return False

    primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
    if primary_key == columns:
        return True

    return any(
        constraint.get("column_names") == columns
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _foreign_keys(inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name) if foreign_key.get("name")}


def _indexes(inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name) if index.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    runtime_columns = _columns(inspector, "runtime_configs")
    if "connection_mode" not in runtime_columns:
        op.add_column("runtime_configs", sa.Column("connection_mode", sa.String(length=20), nullable=True))
    if "connection_configured" not in runtime_columns:
        op.add_column(
            "runtime_configs",
            sa.Column("connection_configured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "connection_verified" not in runtime_columns:
        op.add_column(
            "runtime_configs",
            sa.Column("connection_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "connection_requires_setup" not in runtime_columns:
        op.add_column(
            "runtime_configs",
            sa.Column("connection_requires_setup", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    if "connection_server_url" not in runtime_columns:
        op.add_column("runtime_configs", sa.Column("connection_server_url", sa.Text(), nullable=True))

    inspector = inspect(bind)
    if "ck_runtime_configs_connection_mode" not in _constraints(inspector, "runtime_configs"):
        op.create_check_constraint(
            "ck_runtime_configs_connection_mode",
            "runtime_configs",
            "connection_mode IS NULL OR connection_mode IN ('CLIENT', 'SERVER_PC', 'SERVER')",
        )

    sync_device_columns = _columns(inspector, "sync_devices")
    if "connection_mode" not in sync_device_columns:
        op.add_column("sync_devices", sa.Column("connection_mode", sa.String(length=20), nullable=True))
    inspector = inspect(bind)
    if "ck_sync_devices_connection_mode" not in _constraints(inspector, "sync_devices"):
        op.create_check_constraint(
            "ck_sync_devices_connection_mode",
            "sync_devices",
            "connection_mode IS NULL OR connection_mode IN ('CLIENT', 'SERVER_PC', 'SERVER')",
        )

    audit_columns = _columns(inspector, "audit_logs")
    if "worker_id" not in audit_columns:
        op.add_column("audit_logs", sa.Column("worker_id", sa.Integer(), nullable=True))

    inspector = inspect(bind)
    if "ix_audit_logs_worker_id" not in _indexes(inspector, "audit_logs"):
        op.create_index("ix_audit_logs_worker_id", "audit_logs", ["worker_id"], unique=False)
    # Some historical V1 databases have a populated workers.id column but no declared
    # primary/unique key. Keep the V2 audit context upgradeable for those installations.
    if (
        "fk_audit_logs_worker_id" not in _foreign_keys(inspector, "audit_logs")
        and _has_unique_key(inspector, "workers", ["id"])
    ):
        op.create_foreign_key("fk_audit_logs_worker_id", "audit_logs", "workers", ["worker_id"], ["id"])
    if "device_uuid" not in audit_columns:
        op.add_column("audit_logs", sa.Column("device_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = inspect(bind)
    if "ix_audit_logs_device_uuid" not in _indexes(inspector, "audit_logs"):
        op.create_index("ix_audit_logs_device_uuid", "audit_logs", ["device_uuid"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    audit_columns = _columns(inspector, "audit_logs")
    if "device_uuid" in audit_columns:
        op.drop_index("ix_audit_logs_device_uuid", table_name="audit_logs")
        op.drop_column("audit_logs", "device_uuid")
    if "worker_id" in audit_columns:
        if "ix_audit_logs_worker_id" in _indexes(inspect(bind), "audit_logs"):
            op.drop_index("ix_audit_logs_worker_id", table_name="audit_logs")
        if "fk_audit_logs_worker_id" in _foreign_keys(inspect(bind), "audit_logs"):
            op.drop_constraint("fk_audit_logs_worker_id", "audit_logs", type_="foreignkey")
        op.drop_column("audit_logs", "worker_id")

    if "ck_sync_devices_connection_mode" in _constraints(inspect(bind), "sync_devices"):
        op.drop_constraint("ck_sync_devices_connection_mode", "sync_devices", type_="check")
    if "connection_mode" in _columns(inspect(bind), "sync_devices"):
        op.drop_column("sync_devices", "connection_mode")

    if "ck_runtime_configs_connection_mode" in _constraints(inspect(bind), "runtime_configs"):
        op.drop_constraint("ck_runtime_configs_connection_mode", "runtime_configs", type_="check")
    for column in [
        "connection_server_url",
        "connection_requires_setup",
        "connection_verified",
        "connection_configured",
        "connection_mode",
    ]:
        if column in _columns(inspect(bind), "runtime_configs"):
            op.drop_column("runtime_configs", column)
