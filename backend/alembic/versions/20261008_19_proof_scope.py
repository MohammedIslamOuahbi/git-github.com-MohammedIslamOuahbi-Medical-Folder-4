"""P2-A key/delegation scope."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261008_19"; down_revision="20261008_18"; branch_labels=None; depends_on=None
def upgrade():
 op.add_column("proof_trusted_keys",sa.Column("origin_device_uuid",postgresql.UUID(as_uuid=True),nullable=True))
 op.create_index("ix_proof_trusted_keys_scope","proof_trusted_keys",["clinic_uuid","origin_service_uuid","origin_device_uuid"])
def downgrade(): raise RuntimeError("PROOF_SCOPE_DOWNGRADE_UNSAFE")
