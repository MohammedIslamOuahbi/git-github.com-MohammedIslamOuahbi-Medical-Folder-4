"""retain legacy receipt idempotency for pre-publisher events"""
from alembic import op
revision = "20261008_10"
down_revision = "20261008_09"
branch_labels = None
depends_on = None
def upgrade():
    op.create_unique_constraint("uq_sync_publication_receipt_legacy", "sync_publication_receipts", ["event_uuid", "peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel"])
def downgrade():
    op.drop_constraint("uq_sync_publication_receipt_legacy", "sync_publication_receipts", type_="unique")
