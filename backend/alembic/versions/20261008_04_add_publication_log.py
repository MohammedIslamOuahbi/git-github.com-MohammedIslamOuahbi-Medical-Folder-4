"""Add committed publication log and per-source channel counters."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
revision = "20261008_04"
down_revision = "20261008_03"
branch_labels = None
depends_on = None
def upgrade() -> None:
    existing=set(inspect(op.get_bind()).get_table_names())
    if "sync_publication_counters" in existing and "sync_event_publications" in existing:
        return
    op.create_table("sync_publication_counters", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("source_device_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_generation_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("channel", sa.String(40), nullable=False), sa.Column("next_sequence", sa.BigInteger(), nullable=False, server_default="1"), sa.UniqueConstraint("source_device_uuid", "source_generation_uuid", "channel", name="uq_sync_pub_counter"))
    op.create_table("sync_event_publications", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("event_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_device_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_generation_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("channel", sa.String(40), nullable=False), sa.Column("publish_sequence", sa.BigInteger(), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("event_uuid", "source_device_uuid", "source_generation_uuid", "channel", name="uq_sync_event_publication"))
    op.create_index("ix_sync_event_publications_event", "sync_event_publications", ["event_uuid"])
def downgrade() -> None:
    raise RuntimeError("Refusing to remove publication evidence")
