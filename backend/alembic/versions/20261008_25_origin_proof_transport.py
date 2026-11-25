from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_25'; down_revision='20261008_24'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('origin_proof_transport_receipts',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('proof_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('event_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('content_sha256',sa.String(64),nullable=False),sa.Column('peer_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('source_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('source_generation_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('channel',sa.String(40),nullable=False),sa.Column('proof',sa.JSON(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),sa.Column('acknowledged_at',sa.DateTime(timezone=True)),sa.UniqueConstraint('proof_uuid','peer_device_uuid',name='uq_origin_proof_receipt_peer'))
 op.create_index('ix_origin_proof_receipts_proof_uuid','origin_proof_transport_receipts',['proof_uuid'])
 op.create_index('ix_origin_proof_receipts_event_uuid','origin_proof_transport_receipts',['event_uuid'])
def downgrade(): raise RuntimeError('ORIGIN_PROOF_TRANSPORT_DOWNGRADE_UNSAFE')
