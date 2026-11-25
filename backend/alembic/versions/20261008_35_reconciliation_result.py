"""persist reconciliation result with its leased task"""
from alembic import op
import sqlalchemy as sa
revision = "20261008_35"
down_revision = "20261008_34"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("origin_proof_reconciliation_tasks", sa.Column("result_payload", sa.JSON(), nullable=True))
    op.add_column("origin_proof_reconciliation_tasks", sa.Column("result_fingerprint", sa.String(length=64), nullable=True))
def downgrade():
    op.drop_column("origin_proof_reconciliation_tasks", "result_fingerprint")
    op.drop_column("origin_proof_reconciliation_tasks", "result_payload")
