from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261008_32"; down_revision="20261008_31"; branch_labels=None; depends_on=None
def upgrade():
 op.create_table("origin_proof_reconciliation_tasks",
  sa.Column("task_uuid",postgresql.UUID(as_uuid=True),primary_key=True), sa.Column("event_uuid",postgresql.UUID(as_uuid=True),nullable=False), sa.Column("proof_uuid",postgresql.UUID(as_uuid=True),nullable=False), sa.Column("peer_device_uuid",postgresql.UUID(as_uuid=True),nullable=False), sa.Column("chain_scope",sa.String(160),nullable=False), sa.Column("state",sa.String(20),nullable=False), sa.Column("attempts",sa.Integer(),nullable=False), sa.Column("available_at",sa.DateTime(timezone=True),nullable=False), sa.Column("lease_until",sa.DateTime(timezone=True),nullable=True), sa.Column("claimed_by",sa.String(120),nullable=True), sa.Column("last_error",sa.String(240),nullable=True), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint("event_uuid","proof_uuid","peer_device_uuid","chain_scope",name="uq_origin_proof_reconcile_task"))
def downgrade(): op.drop_table("origin_proof_reconciliation_tasks")
