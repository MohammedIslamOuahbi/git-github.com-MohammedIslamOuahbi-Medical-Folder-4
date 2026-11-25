"""scope transport positions by publisher identity"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_09"
down_revision = "20261008_08"
branch_labels = None
depends_on = None
def upgrade():
    for table in ("sync_publication_counters", "sync_publication_receipts", "sync_transport_cursors"):
        op.add_column(table, sa.Column("publisher_device_uuid", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("publisher_generation_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("sync_event_deliveries", sa.Column("publisher_device_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("sync_event_deliveries", sa.Column("publisher_generation_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_sync_pub_counter_publisher", "sync_publication_counters", ["publisher_device_uuid", "publisher_generation_uuid", "channel"])
    op.create_index("ix_sync_receipt_publisher", "sync_publication_receipts", ["publisher_device_uuid", "publisher_generation_uuid", "channel"])
    op.create_index("ix_sync_cursor_publisher", "sync_transport_cursors", ["publisher_device_uuid", "publisher_generation_uuid", "channel"])
    op.drop_constraint("uq_sync_publication_receipt", "sync_publication_receipts", type_="unique")
    op.create_unique_constraint("uq_sync_publication_receipt_publisher", "sync_publication_receipts", ["event_uuid", "peer_device_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel"])
def downgrade():
    op.drop_constraint("uq_sync_publication_receipt_publisher", "sync_publication_receipts", type_="unique")
    op.create_unique_constraint("uq_sync_publication_receipt", "sync_publication_receipts", ["event_uuid", "peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel"])
    for name, table in (("ix_sync_cursor_publisher","sync_transport_cursors"),("ix_sync_receipt_publisher","sync_publication_receipts"),("ix_sync_pub_counter_publisher","sync_publication_counters")):
        op.drop_index(name, table_name=table)
    for table in ("sync_event_deliveries", "sync_transport_cursors", "sync_publication_receipts", "sync_publication_counters"):
        op.drop_column(table, "publisher_generation_uuid"); op.drop_column(table, "publisher_device_uuid")
