"""complete publisher scope contract; preserve legacy rows as historical"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_11"
down_revision = "20261008_10"
branch_labels = None
depends_on = None
def upgrade():
    for table in ("sync_publication_receipts", "sync_transport_cursors", "sync_event_deliveries"):
        op.add_column(table, sa.Column("clinic_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("sync_publication_receipts", sa.Column("historical_scope_status", sa.String(30), nullable=False, server_default="current"))
    op.add_column("sync_transport_cursors", sa.Column("historical_scope_status", sa.String(30), nullable=False, server_default="current"))
    op.add_column("sync_event_deliveries", sa.Column("historical_scope_status", sa.String(30), nullable=False, server_default="current"))
    op.drop_constraint("uq_sync_publication_receipt_legacy", "sync_publication_receipts", type_="unique")
    op.create_unique_constraint("uq_sync_receipt_publisher_scope", "sync_publication_receipts", ["event_uuid", "peer_device_uuid", "clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel"])
    op.create_unique_constraint("uq_sync_receipt_publisher_position", "sync_publication_receipts", ["peer_device_uuid", "clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel", "publish_sequence"])
    op.create_index("ix_sync_receipt_scope", "sync_publication_receipts", ["clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel", "peer_device_uuid"])
    op.create_index("ix_sync_cursor_scope", "sync_transport_cursors", ["clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel", "peer_device_uuid"])
def downgrade():
    op.drop_index("ix_sync_cursor_scope", table_name="sync_transport_cursors")
    op.drop_index("ix_sync_receipt_scope", table_name="sync_publication_receipts")
    op.drop_constraint("uq_sync_receipt_publisher_position", "sync_publication_receipts", type_="unique")
    op.drop_constraint("uq_sync_receipt_publisher_scope", "sync_publication_receipts", type_="unique")
    op.create_unique_constraint("uq_sync_publication_receipt_legacy", "sync_publication_receipts", ["event_uuid", "peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel"])
    for table in ("sync_event_deliveries", "sync_transport_cursors", "sync_publication_receipts"):
        op.drop_column(table, "historical_scope_status"); op.drop_column(table, "clinic_uuid")
