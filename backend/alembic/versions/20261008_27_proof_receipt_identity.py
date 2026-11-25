from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20261008_27'; down_revision='20261008_26'; branch_labels=None; depends_on=None
def upgrade():
 op.add_column('origin_proof_transport_receipts',sa.Column('receipt_uuid',postgresql.UUID(as_uuid=True),nullable=True))
 op.execute('UPDATE origin_proof_transport_receipts SET receipt_uuid = gen_random_uuid() WHERE receipt_uuid IS NULL')
 op.alter_column('origin_proof_transport_receipts','receipt_uuid',nullable=False)
 op.create_unique_constraint('uq_origin_proof_transport_receipt_uuid','origin_proof_transport_receipts',['receipt_uuid'])
def downgrade(): raise RuntimeError('PROOF_RECEIPT_IDENTITY_DOWNGRADE_UNSAFE')
