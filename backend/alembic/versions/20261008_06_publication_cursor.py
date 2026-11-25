"""add publication cursor fields and receipt position uniqueness"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261008_06"
down_revision = "20261008_05"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sync_transport_cursors", sa.Column("last_publish_sequence", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("sync_transport_cursors", sa.Column("last_publication_event_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint("uq_sync_publication_receipt_position", "sync_publication_receipts",
        ["peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", "publish_sequence"])

def downgrade():
    op.drop_constraint("uq_sync_publication_receipt_position", "sync_publication_receipts", type_="unique")
    op.drop_column("sync_transport_cursors", "last_publication_event_uuid")
    op.drop_column("sync_transport_cursors", "last_publish_sequence")
