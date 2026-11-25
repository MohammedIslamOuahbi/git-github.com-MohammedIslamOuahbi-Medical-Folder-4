"""add prescriptions

Revision ID: 20260610_01
Revises: 20260608_01
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260610_01"
down_revision = "20260608_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "prescriptions" not in existing_tables:
        op.create_table(
            "prescriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("worker_id", sa.Integer(), nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=True),
            sa.Column("prescription_number", sa.String(length=100), nullable=False),
            sa.Column("prescription_date", sa.Date(), nullable=False),
            sa.Column("diagnosis", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["campaign_id"], ["medical_campaigns.id"]),
            sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_prescriptions_id"), "prescriptions", ["id"], unique=False)
        op.create_index(op.f("ix_prescriptions_worker_id"), "prescriptions", ["worker_id"], unique=False)
        op.create_index(op.f("ix_prescriptions_campaign_id"), "prescriptions", ["campaign_id"], unique=False)
        op.create_index(op.f("ix_prescriptions_doctor_id"), "prescriptions", ["doctor_id"], unique=False)
        op.create_index(op.f("ix_prescriptions_status"), "prescriptions", ["status"], unique=False)
        op.create_index(op.f("ix_prescriptions_prescription_date"), "prescriptions", ["prescription_date"], unique=False)
        op.create_index(op.f("ix_prescriptions_prescription_number"), "prescriptions", ["prescription_number"], unique=True)

    if "prescription_items" in existing_tables:
        return

    op.create_table(
        "prescription_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prescription_id", sa.Integer(), nullable=False),
        sa.Column("medication_name", sa.String(length=255), nullable=False),
        sa.Column("dosage", sa.String(length=255), nullable=True),
        sa.Column("frequency", sa.String(length=255), nullable=True),
        sa.Column("duration", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.String(length=255), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prescription_items_id"), "prescription_items", ["id"], unique=False)
    op.create_index(op.f("ix_prescription_items_prescription_id"), "prescription_items", ["prescription_id"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "prescription_items" in existing_tables:
        op.drop_index(op.f("ix_prescription_items_prescription_id"), table_name="prescription_items")
        op.drop_index(op.f("ix_prescription_items_id"), table_name="prescription_items")
        op.drop_table("prescription_items")

    if "prescriptions" in existing_tables:
        op.drop_index(op.f("ix_prescriptions_prescription_number"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_prescription_date"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_status"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_doctor_id"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_campaign_id"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_worker_id"), table_name="prescriptions")
        op.drop_index(op.f("ix_prescriptions_id"), table_name="prescriptions")
        op.drop_table("prescriptions")
