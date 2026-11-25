"""Add durable delivery leases and fencing tokens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "20261008_03"
down_revision = "20261008_02"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind=op.get_bind(); cols={c["name"] for c in inspect(bind).get_columns("sync_event_deliveries")}
    if "lease_token" not in cols: op.add_column("sync_event_deliveries", sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True))
    if "lease_expires_at" not in cols: op.add_column("sync_event_deliveries", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_sync_event_deliveries_lease" not in {i["name"] for i in inspect(bind).get_indexes("sync_event_deliveries")}: op.create_index("ix_sync_event_deliveries_lease", "sync_event_deliveries", ["status", "lease_expires_at"])

def downgrade() -> None:
    raise RuntimeError("Refusing to remove delivery lease evidence")
