"""add client sync package history metadata

Revision ID: 20260714_01
Revises: 20260713_01
Create Date: 2026-07-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260714_01"
down_revision = "20260713_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_local_sync_runs", sa.Column("package_id", sa.String(length=128), nullable=True))
    op.add_column("client_local_sync_runs", sa.Column("package_name", sa.String(length=255), nullable=True))
    op.add_column("client_local_sync_runs", sa.Column("checksum_sha256", sa.String(length=128), nullable=True))
    op.add_column("client_local_sync_runs", sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("client_local_sync_runs", sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("client_local_sync_runs", sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_client_local_sync_runs_checksum_sha256", "client_local_sync_runs", ["checksum_sha256"])
    op.create_index("ix_client_local_sync_runs_package_id", "client_local_sync_runs", ["package_id"])


def downgrade() -> None:
    op.drop_index("ix_client_local_sync_runs_package_id", table_name="client_local_sync_runs")
    op.drop_index("ix_client_local_sync_runs_checksum_sha256", table_name="client_local_sync_runs")
    op.drop_column("client_local_sync_runs", "attachment_count")
    op.drop_column("client_local_sync_runs", "skipped_count")
    op.drop_column("client_local_sync_runs", "duration_ms")
    op.drop_column("client_local_sync_runs", "checksum_sha256")
    op.drop_column("client_local_sync_runs", "package_name")
    op.drop_column("client_local_sync_runs", "package_id")
