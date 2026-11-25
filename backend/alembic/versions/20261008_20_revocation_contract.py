"""P2-A immutable signed revocation records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261008_20"; down_revision="20261008_19"; branch_labels=None; depends_on=None
def upgrade():
 op.add_column("proof_revocations",sa.Column("authority_key_id",sa.String(120),nullable=False,server_default=""))
 op.add_column("proof_revocations",sa.Column("policy_version",sa.String(40),nullable=False,server_default="5A-P1-20261014"))
 op.add_column("proof_revocations",sa.Column("signature",sa.Text(),nullable=False,server_default=""))
 op.add_column("proof_revocations",sa.Column("canonicalization_version",sa.String(80),nullable=False,server_default="deterministic-json-restricted-v1"))
 op.add_column("proof_revocations",sa.Column("target_clinic_uuid",postgresql.UUID(as_uuid=True),nullable=True))
 op.add_column("proof_revocations",sa.Column("target_origin_service_uuid",postgresql.UUID(as_uuid=True),nullable=True))
def downgrade(): raise RuntimeError("PROOF_REVOCATION_DOWNGRADE_UNSAFE")
