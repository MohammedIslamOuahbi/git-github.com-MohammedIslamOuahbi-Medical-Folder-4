from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_29'; down_revision='20261008_28'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('proof_revocation_checkpoints',sa.Column('checkpoint_uuid',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('authority_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('authority_key_id',sa.String(120),nullable=False),sa.Column('chain_scope',sa.String(160),nullable=False),sa.Column('contract_version',sa.String(40),nullable=False),sa.Column('policy_version',sa.String(40),nullable=False),sa.Column('covered_sequence',sa.Integer(),nullable=False),sa.Column('covered_chain_hash',sa.String(64),nullable=False),sa.Column('challenge',sa.String(120),nullable=False),sa.Column('destination_device_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('canonicalization_version',sa.String(80),nullable=False),sa.Column('signature',sa.Text(),nullable=False),sa.Column('is_current',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('authority_uuid','chain_scope','covered_sequence',name='uq_revocation_checkpoint_sequence'))
 op.create_index('ix_revocation_checkpoint_scope','proof_revocation_checkpoints',['authority_uuid','chain_scope'])
def downgrade():
 op.drop_index('ix_revocation_checkpoint_scope',table_name='proof_revocation_checkpoints'); op.drop_table('proof_revocation_checkpoints')
