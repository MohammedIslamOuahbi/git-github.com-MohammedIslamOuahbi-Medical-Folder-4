"""backfill missing sync mixin columns

Revision ID: 20260721_01
Revises: 20260720_01
Create Date: 2026-07-21 09:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260721_01"
down_revision = "20260720_01"
branch_labels = None
depends_on = None


SYNC_STATUS_DEFAULTS: dict[str, str] = {
    "permissions": "synced",
    "user_permissions": "synced",
    "medical_tests": "synced",
    "campaign_workers": "synced",
    "campaign_tests": "synced",
    "doctor_campaigns": "synced",
    "assistant_campaigns": "synced",
    "prescriptions": "synced",
    "prescription_items": "synced",
    "orientation_certificates": "synced",
    "aptitude_certificates": "synced",
}

LOCAL_ID_TABLES = [
    "permissions",
    "user_permissions",
    "medical_tests",
    "campaign_workers",
    "campaign_tests",
    "doctor_campaigns",
    "assistant_campaigns",
    "medical_visits",
    "prescriptions",
    "prescription_items",
    "orientation_certificates",
    "aptitude_certificates",
]


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {item["name"] for item in inspector.get_unique_constraints(table_name)}


def _add_sync_status_if_missing(inspector, table_name: str, default_value: str) -> None:
    if "sync_status" in _column_names(inspector, table_name):
        return

    op.add_column(
        table_name,
        sa.Column("sync_status", sa.String(length=20), nullable=True, server_default=default_value),
    )
    op.execute(
        sa.text(f"UPDATE {table_name} SET sync_status = :default_value WHERE sync_status IS NULL").bindparams(
            default_value=default_value
        )
    )
    op.alter_column(table_name, "sync_status", nullable=False)


def _add_local_id_if_missing(inspector, table_name: str) -> None:
    if "local_id" not in _column_names(inspector, table_name):
        op.add_column(table_name, sa.Column("local_id", sa.String(length=100), nullable=True))

    constraint_name = f"uq_{table_name}_local_id"
    if constraint_name not in _unique_names(inspector, table_name):
        op.create_unique_constraint(constraint_name, table_name, ["local_id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table_name, default_value in SYNC_STATUS_DEFAULTS.items():
        if _table_exists(inspector, table_name):
            _add_sync_status_if_missing(inspector, table_name, default_value)

    for table_name in LOCAL_ID_TABLES:
        if _table_exists(inspector, table_name):
            _add_local_id_if_missing(inspector, table_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table_name in reversed(LOCAL_ID_TABLES):
        if _table_exists(inspector, table_name) and "local_id" in _column_names(inspector, table_name):
            constraint_name = f"uq_{table_name}_local_id"
            if constraint_name in _unique_names(inspector, table_name):
                op.drop_constraint(constraint_name, table_name, type_="unique")
            op.drop_column(table_name, "local_id")

    for table_name in reversed(list(SYNC_STATUS_DEFAULTS.keys())):
        if _table_exists(inspector, table_name) and "sync_status" in _column_names(inspector, table_name):
            op.drop_column(table_name, "sync_status")
