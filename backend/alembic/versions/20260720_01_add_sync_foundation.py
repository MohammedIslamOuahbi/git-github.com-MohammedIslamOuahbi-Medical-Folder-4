"""add sync foundation

Revision ID: 20260720_01
Revises: 20260718_05
Create Date: 2026-07-20 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260720_01"
down_revision = "20260718_05"
branch_labels = None
depends_on = None


SYNCABLE_TABLES = [
    "permissions",
    "users",
    "user_permissions",
    "companies",
    "branches",
    "drilling_sites",
    "medical_tests",
    "medical_campaigns",
    "workspaces",
    "workers",
    "campaign_workers",
    "campaign_tests",
    "doctor_campaigns",
    "assistant_campaigns",
    "medical_visits",
    "worker_tests",
    "prescriptions",
    "prescription_items",
    "orientation_certificates",
    "aptitude_certificates",
]


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)} if _table_exists(inspector, table_name) else set()


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)} if _table_exists(inspector, table_name) else set()


def _unique_names(inspector, table_name: str) -> set[str]:
    return {item["name"] for item in inspector.get_unique_constraints(table_name)} if _table_exists(inspector, table_name) else set()


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(inspector, table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str], *, unique: bool = False, postgresql_where=None) -> None:
    if index_name not in _index_names(inspector, table_name):
        op.create_index(index_name, table_name, columns, unique=unique, postgresql_where=postgresql_where)


def _create_unique_if_missing(inspector, table_name: str, constraint_name: str, columns: list[str]) -> None:
    if constraint_name not in _unique_names(inspector, table_name):
        op.create_unique_constraint(constraint_name, table_name, columns)


def _add_sync_metadata(inspector, table_name: str) -> None:
    _add_column_if_missing(
        inspector,
        table_name,
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=True, server_default=sa.text("gen_random_uuid()")),
    )
    _add_column_if_missing(inspector, table_name, sa.Column("sync_version", sa.Integer(), nullable=True, server_default="1"))
    _add_column_if_missing(inspector, table_name, sa.Column("origin_device_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("last_modified_device_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("origin_mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("last_modified_mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("central_version", sa.Integer(), nullable=True))
    _add_column_if_missing(
        inspector,
        table_name,
        sa.Column("central_sync_status", sa.String(length=30), nullable=True, server_default="never_submitted"),
    )
    _add_column_if_missing(inspector, table_name, sa.Column("central_sequence", sa.BigInteger(), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("central_finalized_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(inspector, table_name, sa.Column("central_server_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text(f"UPDATE {table_name} SET uuid = gen_random_uuid() WHERE uuid IS NULL"))
    op.execute(sa.text(f"UPDATE {table_name} SET sync_version = 1 WHERE sync_version IS NULL"))
    op.execute(sa.text(f"UPDATE {table_name} SET central_sync_status = 'never_submitted' WHERE central_sync_status IS NULL"))
    op.alter_column(table_name, "uuid", nullable=False)
    op.alter_column(table_name, "sync_version", nullable=False)
    op.alter_column(table_name, "central_sync_status", nullable=False)
    _create_unique_if_missing(inspector, table_name, f"uq_{table_name}_uuid", ["uuid"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    if _table_exists(inspector, "medical_visits"):
        columns = _column_names(inspector, "medical_visits")
        if "uuid" in columns:
            op.execute(
                sa.text(
                    """
                    ALTER TABLE medical_visits
                    ALTER COLUMN uuid TYPE uuid
                    USING NULLIF(uuid::text, '')::uuid
                    """
                )
            )
        if "worker_uuid" in columns:
            op.execute(
                sa.text(
                    """
                    ALTER TABLE medical_visits
                    ALTER COLUMN worker_uuid TYPE uuid
                    USING NULLIF(worker_uuid::text, '')::uuid
                    """
                )
            )
        if "campaign_uuid" in columns:
            op.execute(
                sa.text(
                    """
                    ALTER TABLE medical_visits
                    ALTER COLUMN campaign_uuid TYPE uuid
                    USING NULLIF(campaign_uuid::text, '')::uuid
                    """
                )
            )

    for table_name in SYNCABLE_TABLES:
        if _table_exists(inspector, table_name):
            _add_sync_metadata(inspector, table_name)

    if not _table_exists(inspector, "sync_devices"):
        op.create_table(
            "sync_devices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("installation_uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("device_code", sa.String(length=100), nullable=False),
            sa.Column("device_name", sa.String(length=255), nullable=False),
            sa.Column("hostname", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("device_category", sa.String(length=50), nullable=False, server_default="desktop"),
            sa.Column("is_central_server", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_local_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_mission_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_central_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("app_version", sa.String(length=100), nullable=True),
            sa.Column("schema_revision", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("uuid", name="uq_sync_devices_uuid"),
            sa.UniqueConstraint("installation_uuid", name="uq_sync_devices_installation_uuid"),
            sa.UniqueConstraint("device_code", name="uq_sync_devices_device_code"),
        )

    if not _table_exists(inspector, "runtime_configs"):
        op.create_table(
            "runtime_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("runtime_mode", sa.String(length=30), nullable=False, server_default="standalone"),
            sa.Column("active_api_url", sa.Text(), nullable=False),
            sa.Column("local_api_url", sa.Text(), nullable=False),
            sa.Column("mission_server_url", sa.Text(), nullable=True),
            sa.Column("mission_server_device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("active_mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("local_database_write_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_mode_change_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_mode_change_by_user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("runtime_mode IN ('standalone', 'mission_server', 'mission_client')", name="ck_runtime_configs_mode"),
        )

    if not _table_exists(inspector, "mission_sessions"):
        op.create_table(
            "mission_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("mission_code", sa.String(length=120), nullable=False),
            sa.Column("mission_name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("server_device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("server_device_name_snapshot", sa.String(length=255), nullable=False),
            sa.Column("created_by_user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="preparing"),
            sa.Column("base_central_server_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("base_central_generation_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("base_central_sequence", sa.BigInteger(), nullable=True),
            sa.Column("mission_current_sequence", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("finalization_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("centralization_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("centralized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("abort_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("uuid", name="uq_mission_sessions_uuid"),
            sa.UniqueConstraint("mission_code", name="uq_mission_sessions_mission_code"),
            sa.CheckConstraint(
                "status IN ('preparing', 'active', 'finalizing', 'finalized', 'central_pending', 'centralizing', 'centralized', 'aborted', 'failed')",
                name="ck_mission_sessions_status",
            ),
        )

    if not _table_exists(inspector, "mission_session_devices"):
        op.create_table(
            "mission_session_devices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_code_snapshot", sa.String(length=100), nullable=False),
            sa.Column("device_name_snapshot", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_pulled_mission_sequence", sa.BigInteger(), nullable=True),
            sa.Column("last_successful_pull_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("local_copy_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="invited"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("uuid", name="uq_mission_session_devices_uuid"),
            sa.CheckConstraint("role IN ('mission_server', 'mission_client')", name="ck_mission_session_devices_role"),
            sa.CheckConstraint("status IN ('invited', 'connected', 'active', 'syncing', 'copied', 'disconnected', 'revoked')", name="ck_mission_session_devices_status"),
        )

    if not _table_exists(inspector, "sync_changes"):
        op.create_table(
            "sync_changes",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("change_uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("entity_type", sa.String(length=100), nullable=False),
            sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("operation", sa.String(length=20), nullable=False),
            sa.Column("base_version", sa.Integer(), nullable=True),
            sa.Column("entity_version", sa.Integer(), nullable=False),
            sa.Column("changed_fields", sa.JSON(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("source_device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("mission_server_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("mission_sequence", sa.BigInteger(), nullable=True),
            sa.Column("central_server_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("central_sequence", sa.BigInteger(), nullable=True),
            sa.Column("central_status", sa.String(length=30), nullable=False, server_default="never_submitted"),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("mission_committed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("copied_to_client_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_to_central_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("central_accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("central_finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.UniqueConstraint("change_uuid", name="uq_sync_changes_change_uuid"),
            sa.CheckConstraint("operation IN ('insert', 'update', 'delete')", name="ck_sync_changes_operation"),
            sa.CheckConstraint("entity_version >= 1", name="ck_sync_changes_entity_version"),
            sa.CheckConstraint("mission_sequence IS NULL OR mission_sequence >= 1", name="ck_sync_changes_mission_sequence"),
            sa.CheckConstraint("central_sequence IS NULL OR central_sequence >= 1", name="ck_sync_changes_central_sequence"),
            sa.CheckConstraint("retry_count >= 0", name="ck_sync_changes_retry_count"),
        )

    if not _table_exists(inspector, "device_sync_states"):
        op.create_table(
            "device_sync_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("remote_server_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("remote_server_type", sa.String(length=30), nullable=False),
            sa.Column("remote_server_url", sa.Text(), nullable=False),
            sa.Column("mission_session_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("last_pulled_sequence", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("last_pushed_sequence", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("last_push_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_pull_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_failed_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("is_sync_running", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("current_run_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("remote_server_type IN ('mission_server', 'central_server')", name="ck_device_sync_states_remote_type"),
        )

    _create_index_if_missing(inspector, "sync_changes", "ix_sync_changes_mission_pull", ["mission_session_uuid", "mission_sequence"])
    _create_index_if_missing(
        inspector,
        "sync_changes",
        "ix_sync_changes_central_pull",
        ["central_sequence"],
        postgresql_where=sa.text("central_sequence IS NOT NULL"),
    )
    _create_index_if_missing(inspector, "sync_changes", "ix_sync_changes_entity", ["entity_type", "entity_uuid"])
    _create_index_if_missing(
        inspector,
        "sync_changes",
        "ix_sync_changes_central_pending",
        ["mission_sequence"],
        postgresql_where=sa.text("central_status IN ('never_submitted', 'central_pending')"),
    )
    _create_index_if_missing(
        inspector,
        "mission_session_devices",
        "ix_mission_session_devices_session",
        ["mission_session_uuid", "status"],
    )


def downgrade() -> None:
    op.drop_table("device_sync_states")
    op.drop_table("sync_changes")
    op.drop_table("mission_session_devices")
    op.drop_table("mission_sessions")
    op.drop_table("runtime_configs")
    op.drop_table("sync_devices")
