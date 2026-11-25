"""add medical_visit_id to prescriptions

Revision ID: 20260722_01
Revises: 20260721_01
Create Date: 2026-07-22 13:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260722_01"
down_revision = "20260721_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "prescriptions" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("prescriptions")}
    indexes = {index["name"] for index in inspector.get_indexes("prescriptions")}
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("prescriptions")}

    if "medical_visit_id" not in columns:
        op.add_column("prescriptions", sa.Column("medical_visit_id", sa.Integer(), nullable=True))

    if "fk_prescriptions_medical_visit_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_prescriptions_medical_visit_id",
            "prescriptions",
            "medical_visits",
            ["medical_visit_id"],
            ["id"],
        )

    if "ix_prescriptions_medical_visit_id" not in indexes:
        op.create_index("ix_prescriptions_medical_visit_id", "prescriptions", ["medical_visit_id"], unique=False)

    # Backfill only when the mapping is unambiguous: exactly one visit for the same
    # worker, campaign, and prescription date.
    op.execute(
        sa.text(
            """
            WITH unique_matches AS (
                SELECT
                    p.id AS prescription_id,
                    MIN(mv.id) AS medical_visit_id
                FROM prescriptions AS p
                JOIN medical_visits AS mv
                    ON mv.worker_id = p.worker_id
                   AND mv.campaign_id = p.campaign_id
                   AND mv.visit_date = CAST(p.prescription_date AS text)
                WHERE p.medical_visit_id IS NULL
                GROUP BY p.id
                HAVING COUNT(*) = 1
            )
            UPDATE prescriptions AS p
            SET medical_visit_id = unique_matches.medical_visit_id
            FROM unique_matches
            WHERE p.id = unique_matches.prescription_id
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "prescriptions" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("prescriptions")}
    indexes = {index["name"] for index in inspector.get_indexes("prescriptions")}
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("prescriptions")}

    if "ix_prescriptions_medical_visit_id" in indexes:
        op.drop_index("ix_prescriptions_medical_visit_id", table_name="prescriptions")
    if "fk_prescriptions_medical_visit_id" in foreign_keys:
        op.drop_constraint("fk_prescriptions_medical_visit_id", "prescriptions", type_="foreignkey")
    if "medical_visit_id" in columns:
        op.drop_column("prescriptions", "medical_visit_id")
