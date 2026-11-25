from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_05'; down_revision='20261008_04'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('sync_publication_receipts',sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('event_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('peer_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('source_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('source_generation_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('channel',sa.String(40),nullable=False),sa.Column('publish_sequence',sa.BigInteger(),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('event_uuid','peer_device_uuid','source_device_uuid','source_generation_uuid','channel',name='uq_sync_publication_receipt'))
 op.create_index('ix_sync_publication_receipts_cursor','sync_publication_receipts',['peer_device_uuid','source_device_uuid','source_generation_uuid','channel','publish_sequence'])
def downgrade(): raise RuntimeError('Refusing to remove publication receipt evidence')
