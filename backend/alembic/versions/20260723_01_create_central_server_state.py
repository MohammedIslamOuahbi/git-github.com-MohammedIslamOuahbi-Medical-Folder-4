"""create central server state table when missing

Revision ID: 20260723_01
Revises: 20260722_04
Create Date: 2026-07-23 09:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260723_01"
down_revision = "20260722_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "central_server_state" not in tables:
        op.create_table(
            "central_server_state",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("server_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("server_generation_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="inactive"),
            sa.Column("schema_revision", sa.String(length=100), nullable=True),
            sa.Column("protocol_version", sa.String(length=20), nullable=False, server_default="1"),
            sa.Column("current_central_sequence", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["device_uuid"], ["sync_devices.uuid"]),
            sa.UniqueConstraint("server_uuid", name="uq_central_server_state_server_uuid"),
            sa.UniqueConstraint("server_generation_uuid", name="uq_central_server_state_generation_uuid"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("central_server_state")} if "central_server_state" in set(inspector.get_table_names()) else set()
    if "ix_central_server_state_id" not in indexes:
        op.create_index("ix_central_server_state_id", "central_server_state", ["id"], unique=False)
    if "ix_central_server_state_device_uuid" not in indexes:
        op.create_index("ix_central_server_state_device_uuid", "central_server_state", ["device_uuid"], unique=False)
    if "ix_central_server_state_status" not in indexes:
        op.create_index("ix_central_server_state_status", "central_server_state", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "central_server_state" not in set(inspector.get_table_names()):
        return
    for index_name in [
        "ix_central_server_state_status",
        "ix_central_server_state_device_uuid",
        "ix_central_server_state_id",
    ]:
        existing_indexes = {index["name"] for index in inspect(bind).get_indexes("central_server_state")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="central_server_state")
    op.drop_table("central_server_state")
