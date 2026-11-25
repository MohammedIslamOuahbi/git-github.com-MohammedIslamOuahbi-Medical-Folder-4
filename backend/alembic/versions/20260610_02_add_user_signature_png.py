"""add user signature png

Revision ID: 20260610_02
Revises: 20260610_01
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260610_02"
down_revision = "20260610_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "signature_png" in columns:
        return

    op.add_column("users", sa.Column("signature_png", sa.Text(), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "signature_png" not in columns:
        return

    op.drop_column("users", "signature_png")
