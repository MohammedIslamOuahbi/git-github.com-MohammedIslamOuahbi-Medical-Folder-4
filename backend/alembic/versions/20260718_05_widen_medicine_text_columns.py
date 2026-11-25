"""widen medicine text columns for official catalogue import

Revision ID: 20260718_05
Revises: 20260718_04
Create Date: 2026-07-18 20:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260718_05"
down_revision = "20260718_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("medicines", "pharmaceutical_form", existing_type=sa.String(length=255), type_=sa.String(length=500))
    op.alter_column(
        "medicines",
        "source_pharmaceutical_form",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
    )
    op.alter_column("medicines", "strength", existing_type=sa.String(length=255), type_=sa.String(length=500))


def downgrade() -> None:
    op.alter_column("medicines", "strength", existing_type=sa.String(length=500), type_=sa.String(length=255))
    op.alter_column(
        "medicines",
        "source_pharmaceutical_form",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
    )
    op.alter_column("medicines", "pharmaceutical_form", existing_type=sa.String(length=500), type_=sa.String(length=255))
