"""widen installation provisioning status

Revision ID: 20260722_04
Revises: 20260722_03
Create Date: 2026-07-22 23:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260722_04"
down_revision = "20260722_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "installation_state" not in set(inspector.get_table_names()):
        return
    op.alter_column(
        "installation_state",
        "provisioning_status",
        existing_type=sa.String(length=30),
        type_=sa.String(length=100),
        existing_nullable=False,
        existing_server_default="unconfigured",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "installation_state" not in set(inspector.get_table_names()):
        return
    op.alter_column(
        "installation_state",
        "provisioning_status",
        existing_type=sa.String(length=100),
        type_=sa.String(length=30),
        existing_nullable=False,
        existing_server_default="unconfigured",
    )
