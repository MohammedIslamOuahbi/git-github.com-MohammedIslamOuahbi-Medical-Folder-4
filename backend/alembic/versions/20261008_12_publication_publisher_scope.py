"""make publication identity belong to publisher scope; retain legacy NULL rows"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_12"
down_revision = "20261008_11"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sync_publication_counters", sa.Column("clinic_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.drop_constraint("uq_sync_event_publication", "sync_event_publications", type_="unique")
    op.create_unique_constraint("uq_sync_event_publication_publisher_scope", "sync_event_publications", ["event_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel"])
    op.create_unique_constraint("uq_sync_event_publication_publisher_position", "sync_event_publications", ["publisher_device_uuid", "publisher_generation_uuid", "channel", "publish_sequence"])
    op.drop_constraint("uq_sync_pub_counter", "sync_publication_counters", type_="unique")
    op.create_unique_constraint("uq_sync_pub_counter_publisher_scope", "sync_publication_counters", ["clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel"])

def downgrade():
    op.drop_constraint("uq_sync_pub_counter_publisher_scope", "sync_publication_counters", type_="unique")
    op.create_unique_constraint("uq_sync_pub_counter", "sync_publication_counters", ["source_device_uuid", "source_generation_uuid", "channel"])
    op.drop_constraint("uq_sync_event_publication_publisher_position", "sync_event_publications", type_="unique")
    op.drop_constraint("uq_sync_event_publication_publisher_scope", "sync_event_publications", type_="unique")
    op.create_unique_constraint("uq_sync_event_publication", "sync_event_publications", ["event_uuid", "source_device_uuid", "source_generation_uuid", "channel"])
