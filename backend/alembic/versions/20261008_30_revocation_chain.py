from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_30'; down_revision='20261008_29'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('proof_revocation_chain_records',sa.Column('record_uuid',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('authority_uuid',postgresql.UUID(as_uuid=True),nullable=False),sa.Column('chain_scope',sa.String(160),nullable=False),sa.Column('contract_version',sa.String(40),nullable=False),sa.Column('canonicalization_version',sa.String(80),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('previous_record_hash',sa.String(64),nullable=False),sa.Column('record_hash',sa.String(64),nullable=False),sa.Column('record',sa.JSON(),nullable=False),sa.Column('signature',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('authority_uuid','chain_scope','sequence',name='uq_revocation_chain_sequence'))
def downgrade(): op.drop_table('proof_revocation_chain_records')
