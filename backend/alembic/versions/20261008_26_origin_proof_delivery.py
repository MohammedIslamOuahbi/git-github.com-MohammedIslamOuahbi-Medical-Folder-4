from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_26'; down_revision='20261008_25'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('origin_proof_deliveries',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('proof_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('peer_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('channel',sa.String(40),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('attempt_count',sa.Integer(),nullable=False),sa.Column('lease_token',postgresql.UUID(as_uuid=True)),sa.Column('lease_expires_at',sa.DateTime(timezone=True)),sa.Column('delivered_at',sa.DateTime(timezone=True)),sa.Column('last_error_code',sa.String(100)),sa.Column('created_at',sa.DateTime(timezone=True)),sa.UniqueConstraint('proof_uuid','peer_device_uuid','channel',name='uq_origin_proof_delivery_scope'))
def downgrade(): raise RuntimeError('ORIGIN_PROOF_DELIVERY_DOWNGRADE_UNSAFE')
