"""add worker etat actual

Revision ID: 20260630_01
Revises: 20260625_01
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260630_01"
down_revision = "20260625_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("workers")}
    if "etat_actual" in columns:
        return

    op.add_column(
        "workers",
        sa.Column("etat_actual", sa.String(length=50), nullable=False, server_default="present"),
    )
    op.execute(sa.text("UPDATE workers SET etat_actual = 'present' WHERE etat_actual IS NULL OR TRIM(etat_actual) = ''"))
    op.alter_column("workers", "etat_actual", server_default=None)


def downgrade() -> None:
    op.drop_column("workers", "etat_actual")
