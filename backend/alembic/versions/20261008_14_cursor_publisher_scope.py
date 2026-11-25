"""Scope transport cursors by publication publisher."""
from alembic import op
revision='20261008_14'; down_revision='20261008_13'; branch_labels=None; depends_on=None
def upgrade():
    op.drop_constraint('uq_sync_transport_cursor','sync_transport_cursors',type_='unique')
    op.create_unique_constraint('uq_sync_transport_cursor_publisher_scope','sync_transport_cursors',['peer_device_uuid','source_device_uuid','source_generation_uuid','channel','publisher_device_uuid','publisher_generation_uuid','clinic_uuid'])
def downgrade():
    raise RuntimeError('SYNC_CURSOR_SCOPE_DOWNGRADE_UNSAFE')
