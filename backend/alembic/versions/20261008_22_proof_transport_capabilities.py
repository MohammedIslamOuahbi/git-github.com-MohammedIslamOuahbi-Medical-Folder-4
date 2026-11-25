from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_22'; down_revision='20261008_21'; branch_labels=None; depends_on=None
def upgrade():
 op.add_column('proof_transport_capabilities',sa.Column('connection_scope',sa.String(160),nullable=False,server_default='default'))
 op.add_column('proof_transport_capabilities',sa.Column('advertisement_uuid',postgresql.UUID(as_uuid=True),nullable=False,server_default='00000000-0000-0000-0000-000000000000'))
 op.alter_column('proof_transport_capabilities','max_version',new_column_name='proof_transport_version')
 op.drop_constraint('proof_transport_capabilities_pkey','proof_transport_capabilities',type_='primary')
 op.create_primary_key('proof_transport_capabilities_pkey','proof_transport_capabilities',['peer_device_uuid','connection_scope'])
def downgrade(): raise RuntimeError('PROOF_TRANSPORT_CAPABILITY_DOWNGRADE_UNSAFE')
