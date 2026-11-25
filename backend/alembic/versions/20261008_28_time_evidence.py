from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_28'; down_revision='20261008_27'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('proof_time_evidence',
  sa.Column('evidence_uuid',postgresql.UUID(as_uuid=True),primary_key=True),
  sa.Column('proof_uuid',postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column('event_uuid',postgresql.UUID(as_uuid=True),nullable=False),
  sa.Column('content_sha256',sa.String(64),nullable=False),
  sa.Column('chain_scope',sa.String(160),nullable=False),
  sa.Column('sequence',sa.Integer(),nullable=False),
  sa.Column('evidence_sha256',sa.String(64),nullable=False),
  sa.Column('evidence',sa.JSON(),nullable=False),
  sa.Column('validation_result',sa.String(40),nullable=False),
  sa.Column('validation_reason',sa.String(120),nullable=False),
  sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
  sa.UniqueConstraint('proof_uuid','evidence_uuid',name='uq_proof_time_evidence_identity'))
 op.create_index('ix_proof_time_evidence_proof_uuid','proof_time_evidence',['proof_uuid'])
 op.create_index('ix_proof_time_evidence_event_uuid','proof_time_evidence',['event_uuid'])
def downgrade():
 op.drop_index('ix_proof_time_evidence_event_uuid',table_name='proof_time_evidence'); op.drop_index('ix_proof_time_evidence_proof_uuid',table_name='proof_time_evidence'); op.drop_table('proof_time_evidence')
