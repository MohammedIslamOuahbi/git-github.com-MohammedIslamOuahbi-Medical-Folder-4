"""add client sync durable change journal

Revision ID: 20260713_01
Revises: 20260709_01
Create Date: 2026-07-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260713_01"
down_revision = "20260709_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_sync_changes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_sync_changes_actor_user_id", "client_sync_changes", ["actor_user_id"])
    op.create_index("ix_client_sync_changes_changed_at", "client_sync_changes", ["changed_at"])
    op.create_index("ix_client_sync_changes_entity_id", "client_sync_changes", ["entity_id"])
    op.create_index("ix_client_sync_changes_entity_type", "client_sync_changes", ["entity_type"])
    op.create_index("ix_client_sync_changes_operation", "client_sync_changes", ["operation"])
    op.create_index("ix_client_sync_changes_workspace_id", "client_sync_changes", ["workspace_id"])
    op.create_table(
        "client_local_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.String(length=100), nullable=False),
        sa.Column("last_sync_cursor", sa.BigInteger(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("last_package_checksum", sa.String(length=128), nullable=True),
        sa.Column("last_status", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "client_local_sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.String(length=100), nullable=False),
        sa.Column("from_cursor", sa.BigInteger(), nullable=False),
        sa.Column("to_cursor", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("deleted_count", sa.Integer(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_local_sync_runs_server_id", "client_local_sync_runs", ["server_id"])


def downgrade() -> None:
    op.drop_index("ix_client_local_sync_runs_server_id", table_name="client_local_sync_runs")
    op.drop_table("client_local_sync_runs")
    op.drop_table("client_local_sync_state")
    op.drop_index("ix_client_sync_changes_workspace_id", table_name="client_sync_changes")
    op.drop_index("ix_client_sync_changes_operation", table_name="client_sync_changes")
    op.drop_index("ix_client_sync_changes_entity_type", table_name="client_sync_changes")
    op.drop_index("ix_client_sync_changes_entity_id", table_name="client_sync_changes")
    op.drop_index("ix_client_sync_changes_changed_at", table_name="client_sync_changes")
    op.drop_index("ix_client_sync_changes_actor_user_id", table_name="client_sync_changes")
    op.drop_table("client_sync_changes")
