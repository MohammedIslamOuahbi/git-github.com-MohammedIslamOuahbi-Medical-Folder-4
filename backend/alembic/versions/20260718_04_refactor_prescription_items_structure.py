"""refactor prescription items structure

Revision ID: 20260718_04
Revises: 20260718_03
Create Date: 2026-07-18 22:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260718_04"
down_revision = "20260718_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("prescription_items")}

    def add_column(name: str, column: sa.Column) -> None:
        if name not in columns:
            op.add_column("prescription_items", column)

    add_column("medicine_id", sa.Column("medicine_id", sa.Integer(), nullable=True))
    add_column("brand_name", sa.Column("brand_name", sa.String(length=255), nullable=True))
    add_column("generic_name", sa.Column("generic_name", sa.String(length=255), nullable=True))
    add_column("strength", sa.Column("strength", sa.String(length=255), nullable=True))
    add_column("pharmaceutical_form", sa.Column("pharmaceutical_form", sa.String(length=255), nullable=True))
    add_column("dose_quantity", sa.Column("dose_quantity", sa.String(length=50), nullable=True))
    add_column("dose_unit", sa.Column("dose_unit", sa.String(length=100), nullable=True))
    add_column("frequency_custom", sa.Column("frequency_custom", sa.String(length=255), nullable=True))
    add_column("duration_value", sa.Column("duration_value", sa.String(length=50), nullable=True))
    add_column("duration_unit", sa.Column("duration_unit", sa.String(length=50), nullable=True))
    add_column("number_of_boxes", sa.Column("number_of_boxes", sa.String(length=50), nullable=True))
    add_column("sort_order", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    indexes = {index["name"] for index in inspector.get_indexes("prescription_items")}
    if "ix_prescription_items_medicine_id" not in indexes:
        op.create_index("ix_prescription_items_medicine_id", "prescription_items", ["medicine_id"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("prescription_items")}
    if "ix_prescription_items_medicine_id" in indexes:
        op.drop_index("ix_prescription_items_medicine_id", table_name="prescription_items")

    columns = {column["name"] for column in inspector.get_columns("prescription_items")}
    for name in [
        "sort_order",
        "number_of_boxes",
        "duration_unit",
        "duration_value",
        "frequency_custom",
        "dose_unit",
        "dose_quantity",
        "pharmaceutical_form",
        "strength",
        "generic_name",
        "brand_name",
        "medicine_id",
    ]:
        if name in columns:
            op.drop_column("prescription_items", name)
