from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261008_24'
down_revision = '20261008_23'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'origin_proofs',
        sa.Column('proof_uuid', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('request_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_uuid', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('content_sha256', sa.String(length=64), nullable=False),
        sa.Column('signing_key_id', sa.String(length=120), nullable=False),
        sa.Column('proof', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('request_uuid', name='uq_origin_proofs_request'),
    )
    op.create_index('ix_origin_proofs_request_uuid', 'origin_proofs', ['request_uuid'])

def downgrade():
    raise RuntimeError('ORIGIN_PROOFS_DOWNGRADE_UNSAFE')
