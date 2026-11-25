"""add client local sync state package metadata

Revision ID: 20260718_01
Revises: 20260714_01
Create Date: 2026-07-18 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718_01"
down_revision = "20260714_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_local_sync_state", sa.Column("last_package_id", sa.String(length=128), nullable=True))
    op.add_column("client_local_sync_state", sa.Column("last_package_name", sa.String(length=255), nullable=True))
    op.add_column("client_local_sync_state", sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("client_local_sync_state", "last_imported_at")
    op.drop_column("client_local_sync_state", "last_package_name")
    op.drop_column("client_local_sync_state", "last_package_id")
