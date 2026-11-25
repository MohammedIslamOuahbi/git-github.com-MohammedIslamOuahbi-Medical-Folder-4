"""Add source clinic identity to the reusable SyncChange event envelope."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "20261008_02"
down_revision = "20261008_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind(); cols = {c["name"] for c in inspect(bind).get_columns("sync_changes")}
    if "source_clinic_uuid" not in cols:
        op.add_column("sync_changes", sa.Column("source_clinic_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    if "ix_sync_changes_source_clinic_uuid" not in {i["name"] for i in inspect(bind).get_indexes("sync_changes")}:
        op.create_index("ix_sync_changes_source_clinic_uuid", "sync_changes", ["source_clinic_uuid"])


def downgrade() -> None:
    raise RuntimeError("Refusing to remove event identity evidence")
