from alembic import op
import sqlalchemy as sa
revision='20261008_23'; down_revision='20261008_22'; branch_labels=None; depends_on=None
def upgrade():
    op.add_column('proof_transport_capabilities', sa.Column('advertisement_sequence', sa.Integer(), nullable=False, server_default='0'))
def downgrade():
    raise RuntimeError('PROOF_TRANSPORT_CAPABILITY_ORDERING_DOWNGRADE_UNSAFE')
