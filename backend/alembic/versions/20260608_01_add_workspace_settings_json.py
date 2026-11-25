"""add workspace settings json

Revision ID: 20260608_01
Revises: 20260607_01
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260608_01"
down_revision = "20260607_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workspaces")}
    if "settings_json" in columns:
        return

    op.add_column("workspaces", sa.Column("settings_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workspaces")}
    if "settings_json" not in columns:
        return

    op.drop_column("workspaces", "settings_json")
