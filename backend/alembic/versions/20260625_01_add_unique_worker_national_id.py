"""add unique worker national identity number

Revision ID: 20260625_01
Revises: 20260610_02
Create Date: 2026-06-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260625_01"
down_revision = "20260610_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = {index["name"] for index in inspector.get_indexes("workers")}
    if "uq_workers_national_id" in existing_indexes:
        return

    duplicate_rows = conn.execute(
        sa.text(
            """
            SELECT national_id, COUNT(*) AS total
            FROM workers
            WHERE national_id IS NOT NULL AND TRIM(national_id) <> ''
            GROUP BY national_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicate_rows:
        duplicate_values = ", ".join(str(row[0]) for row in duplicate_rows)
        raise RuntimeError(
            "Cannot add unique constraint on workers.national_id because duplicate values already exist: "
            f"{duplicate_values}"
        )

    op.create_index("uq_workers_national_id", "workers", ["national_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_workers_national_id", table_name="workers")
