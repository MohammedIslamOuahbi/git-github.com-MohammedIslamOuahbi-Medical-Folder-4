"""add application initialization metadata

Revision ID: 20260718_02
Revises: 20260718_01
Create Date: 2026-07-18 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718_02"
down_revision = "20260718_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_initialization",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("initialization_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reference_data_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initialized_by_user_id", sa.Integer(), nullable=True),
        sa.Column("initialization_status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["initialized_by_user_id"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("application_initialization")
