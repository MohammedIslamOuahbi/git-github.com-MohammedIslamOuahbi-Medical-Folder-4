"""widen orientation_type_other for postgres compatibility

Revision ID: 20260709_01
Revises: 2f42145e22d3
Create Date: 2026-07-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260709_01"
down_revision = "2f42145e22d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "orientation_certificates" not in tables:
        return

    columns = {column["name"]: column for column in inspector.get_columns("orientation_certificates")}
    target = columns.get("orientation_type_other")
    if not target:
        return

    current_type = str(target["type"]).lower()
    if "text" in current_type:
        return

    op.alter_column(
        "orientation_certificates",
        "orientation_type_other",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "orientation_certificates" not in tables:
        return

    columns = {column["name"]: column for column in inspector.get_columns("orientation_certificates")}
    target = columns.get("orientation_type_other")
    if not target:
        return

    current_type = str(target["type"]).lower()
    if "character varying(100)" in current_type or "varchar(100)" in current_type:
        return

    op.alter_column(
        "orientation_certificates",
        "orientation_type_other",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
