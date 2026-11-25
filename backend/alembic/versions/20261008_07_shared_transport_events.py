"""add canonical durable transport event source"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_07"
down_revision = "20261008_06"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("sync_transport_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_clinic_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_generation_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_sequence", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_uuid", postgresql.UUID(as_uuid=True)),
        sa.Column("parent_revision_uuid", postgresql.UUID(as_uuid=True)),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("origin_kind", sa.String(20), nullable=False, server_default="local"),
        sa.Column("origin_inbox_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_uuid", name="uq_sync_transport_event_uuid"))
    op.create_index("ix_sync_transport_events_source", "sync_transport_events", ["source_clinic_uuid", "source_device_uuid", "source_generation_uuid"])
def downgrade():
    op.drop_index("ix_sync_transport_events_source", table_name="sync_transport_events")
    op.drop_table("sync_transport_events")
