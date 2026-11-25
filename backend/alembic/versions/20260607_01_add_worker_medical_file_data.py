"""add worker medical file data

Revision ID: 20260607_01
Revises:
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260607_01"
down_revision = "20260606_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workers")}
    if "medical_file_data" in columns:
        return

    op.add_column("workers", sa.Column("medical_file_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workers")}
    if "medical_file_data" not in columns:
        return

    op.drop_column("workers", "medical_file_data")
