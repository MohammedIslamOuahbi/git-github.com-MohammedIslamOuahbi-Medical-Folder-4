"""add prescription validator columns

Revision ID: 20260722_02
Revises: 20260722_01
Create Date: 2026-07-22 14:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260722_02"
down_revision = "20260722_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "prescriptions" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("prescriptions")}

    if "include_validator_signature" not in columns:
        op.add_column(
            "prescriptions",
            sa.Column(
                "include_validator_signature",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("prescriptions", "include_validator_signature", server_default=None)

    if "validator_id" not in columns:
        op.add_column("prescriptions", sa.Column("validator_id", sa.Integer(), nullable=True))

    if "validator_name" not in columns:
        op.add_column("prescriptions", sa.Column("validator_name", sa.String(length=255), nullable=True))

    if "validator_role" not in columns:
        op.add_column("prescriptions", sa.Column("validator_role", sa.String(length=100), nullable=True))

    if "validated_at" not in columns:
        op.add_column("prescriptions", sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True))

    if "validator_signature_image_path" not in columns:
        op.add_column("prescriptions", sa.Column("validator_signature_image_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "prescriptions" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("prescriptions")}

    for column_name in [
        "validator_signature_image_path",
        "validated_at",
        "validator_role",
        "validator_name",
        "validator_id",
        "include_validator_signature",
    ]:
        if column_name in columns:
            op.drop_column("prescriptions", column_name)
