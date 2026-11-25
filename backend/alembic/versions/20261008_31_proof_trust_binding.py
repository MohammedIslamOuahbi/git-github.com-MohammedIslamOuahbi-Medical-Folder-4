from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261008_31"; down_revision="20261008_30"; branch_labels=None; depends_on=None
def upgrade():
 op.create_table("proof_trust_bindings",
  sa.Column("binding_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
  sa.Column("signing_key_id", sa.String(120), nullable=False),
  sa.Column("issuer_uuid", postgresql.UUID(as_uuid=True), nullable=True),
  sa.Column("revocation_authority_uuid", postgresql.UUID(as_uuid=True), nullable=False),
  sa.Column("chain_scope", sa.String(160), nullable=False),
  sa.Column("chain_contract_version", sa.String(40), nullable=False),
  sa.Column("clinic_uuid", postgresql.UUID(as_uuid=True), nullable=False),
  sa.Column("origin_service_uuid", postgresql.UUID(as_uuid=True), nullable=False),
  sa.Column("policy_version", sa.String(40), nullable=False),
  sa.Column("state", sa.String(20), nullable=False),
  sa.Column("binding_version", sa.Integer(), nullable=False),
  sa.Column("approval_source", sa.Text(), nullable=False),
  sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
  sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  sa.UniqueConstraint("signing_key_id","issuer_uuid","clinic_uuid","origin_service_uuid","policy_version",name="uq_proof_trust_binding_identity"))
 op.create_index("ix_proof_trust_bindings_signing_key_id","proof_trust_bindings",["signing_key_id"])
def downgrade():
 op.drop_index("ix_proof_trust_bindings_signing_key_id", table_name="proof_trust_bindings"); op.drop_table("proof_trust_bindings")
