"""add installation profile state

Revision ID: 20260722_03
Revises: 20260722_02
Create Date: 2026-07-22 20:55:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, select
from sqlalchemy.dialects import postgresql


revision = "20260722_03"
down_revision = "20260722_02"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "installation_state" not in tables:
        op.create_table(
            "installation_state",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("installation_uuid", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("installation_profile", sa.String(length=30), nullable=True),
            sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("provisioning_status", sa.String(length=30), nullable=False, server_default="unconfigured"),
            sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("provisioned_by_user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("device_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("device_code", sa.String(length=100), nullable=True),
            sa.Column("device_name", sa.String(length=255), nullable=True),
            sa.Column("central_server_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("central_generation_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["device_uuid"], ["sync_devices.uuid"]),
            sa.UniqueConstraint("installation_uuid", name="uq_installation_state_installation_uuid"),
            sa.CheckConstraint(
                "(installation_profile IS NULL OR installation_profile IN ('central_server', 'mobile_device'))",
                name="ck_installation_state_profile",
            ),
            sa.CheckConstraint(
                "provisioning_status IN ('unconfigured', 'provisioning', 'configured', 'failed', 'reset_required')",
                name="ck_installation_state_status",
            ),
        )
        op.create_index("ix_installation_state_id", "installation_state", ["id"], unique=False)
        op.create_index("ix_installation_state_installation_profile", "installation_state", ["installation_profile"], unique=False)
        op.create_index("ix_installation_state_provisioning_status", "installation_state", ["provisioning_status"], unique=False)
        op.create_index("ix_installation_state_device_uuid", "installation_state", ["device_uuid"], unique=False)
        op.create_index("ix_installation_state_central_server_uuid", "installation_state", ["central_server_uuid"], unique=False)
        op.create_index("ix_installation_state_central_generation_uuid", "installation_state", ["central_generation_uuid"], unique=False)

    installation_table = sa.table(
        "installation_state",
        sa.column("installation_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("installation_profile", sa.String()),
        sa.column("profile_version", sa.Integer()),
        sa.column("provisioning_status", sa.String()),
        sa.column("device_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("device_code", sa.String()),
        sa.column("device_name", sa.String()),
        sa.column("central_server_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("central_generation_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    sync_devices = sa.table(
        "sync_devices",
        sa.column("uuid", postgresql.UUID(as_uuid=True)),
        sa.column("installation_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("device_code", sa.String()),
        sa.column("device_name", sa.String()),
        sa.column("is_central_server", sa.Boolean()),
    )
    central_state = sa.table(
        "central_server_state",
        sa.column("device_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("server_uuid", postgresql.UUID(as_uuid=True)),
        sa.column("server_generation_uuid", postgresql.UUID(as_uuid=True)),
    )

    installation_rows = {
        row[0]
        for row in bind.execute(select(installation_table.c.installation_uuid)).all()
        if row[0] is not None
    }
    central_rows = {}
    if "central_server_state" in tables:
        central_rows = {
            row["device_uuid"]: row
            for row in bind.execute(
                select(
                    central_state.c.device_uuid,
                    central_state.c.server_uuid,
                    central_state.c.server_generation_uuid,
                )
            ).mappings().all()
            if row["device_uuid"] is not None
        }
    now = _now()
    if "sync_devices" not in tables:
        return
    for row in bind.execute(
        select(
            sync_devices.c.uuid,
            sync_devices.c.installation_uuid,
            sync_devices.c.device_code,
            sync_devices.c.device_name,
        )
    ).mappings():
        installation_uuid = row["installation_uuid"]
        if installation_uuid is None or installation_uuid in installation_rows:
            continue
        related_central = central_rows.get(row["uuid"])
        bind.execute(
            installation_table.insert().values(
                installation_uuid=installation_uuid,
                installation_profile=None,
                profile_version=1,
                provisioning_status="unconfigured",
                device_uuid=row["uuid"],
                device_code=row["device_code"],
                device_name=row["device_name"],
                central_server_uuid=related_central["server_uuid"] if related_central else None,
                central_generation_uuid=related_central["server_generation_uuid"] if related_central else None,
                created_at=now,
                updated_at=now,
            )
        )
        installation_rows.add(installation_uuid)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "installation_state" not in set(inspector.get_table_names()):
        return
    for index_name in [
        "ix_installation_state_central_generation_uuid",
        "ix_installation_state_central_server_uuid",
        "ix_installation_state_device_uuid",
        "ix_installation_state_provisioning_status",
        "ix_installation_state_installation_profile",
        "ix_installation_state_id",
    ]:
        op.drop_index(index_name, table_name="installation_state")
    op.drop_table("installation_state")
