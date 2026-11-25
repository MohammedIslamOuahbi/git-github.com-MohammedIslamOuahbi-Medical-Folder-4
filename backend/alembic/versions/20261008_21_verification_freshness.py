"""P2-A verification input freshness and immutable history."""
from alembic import op
import sqlalchemy as sa
revision="20261008_21"; down_revision="20261008_20"; branch_labels=None; depends_on=None
def upgrade():
 op.drop_constraint("uq_proof_verification_event_hash","proof_verification_results",type_="unique")
 op.add_column("proof_verification_results",sa.Column("input_fingerprint",sa.String(64),nullable=False,server_default=""))
 op.add_column("proof_verification_results",sa.Column("policy_version",sa.String(40),nullable=False,server_default=""))
 op.create_unique_constraint("uq_proof_verification_event_input","proof_verification_results",["event_uuid","input_fingerprint"])
def downgrade(): raise RuntimeError("PROOF_VERIFICATION_FRESHNESS_DOWNGRADE_UNSAFE")
