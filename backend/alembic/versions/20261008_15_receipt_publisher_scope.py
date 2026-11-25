"""Scope publication receipts by publisher identity."""
from alembic import op
revision='20261008_15'; down_revision='20261008_14'; branch_labels=None; depends_on=None
def upgrade():
    op.execute("ALTER TABLE sync_publication_receipts DROP CONSTRAINT IF EXISTS uq_sync_publication_receipt")
    op.execute("ALTER TABLE sync_publication_receipts DROP CONSTRAINT IF EXISTS uq_sync_publication_receipt_position")
    op.execute("ALTER TABLE sync_publication_receipts DROP CONSTRAINT IF EXISTS uq_sync_publication_receipt_publisher")
    op.execute("ALTER TABLE sync_publication_receipts DROP CONSTRAINT IF EXISTS uq_sync_receipt_publisher_position")
    op.execute("ALTER TABLE sync_publication_receipts DROP CONSTRAINT IF EXISTS uq_sync_receipt_publisher_scope")
    op.create_unique_constraint('uq_sync_publication_receipt_publisher_scope','sync_publication_receipts',['event_uuid','peer_device_uuid','source_device_uuid','source_generation_uuid','channel','publisher_device_uuid','publisher_generation_uuid','clinic_uuid'])
    op.create_unique_constraint('uq_sync_publication_receipt_position_publisher_scope','sync_publication_receipts',['peer_device_uuid','source_device_uuid','source_generation_uuid','channel','publish_sequence','publisher_device_uuid','publisher_generation_uuid','clinic_uuid'])
def downgrade(): raise RuntimeError('SYNC_RECEIPT_SCOPE_DOWNGRADE_UNSAFE')
