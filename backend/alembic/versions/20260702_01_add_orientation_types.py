"""add orientation types json field

Revision ID: 20260702_01
Revises: 20260630_01
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260702_01"
down_revision = "20260630_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "orientation_certificates" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("orientation_certificates")}
    if "orientation_types" in columns:
        return

    op.add_column(
        "orientation_certificates",
        sa.Column("orientation_types", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "orientation_certificates" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("orientation_certificates")}
    if "orientation_types" not in columns:
        return

    op.drop_column("orientation_certificates", "orientation_types")
