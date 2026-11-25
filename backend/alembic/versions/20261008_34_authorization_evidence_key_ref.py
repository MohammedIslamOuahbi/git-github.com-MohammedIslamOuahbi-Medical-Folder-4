from alembic import op
import sqlalchemy as sa
revision="20261008_34"; down_revision="20261008_33"; branch_labels=None; depends_on=None
def upgrade():
 op.add_column("authorization_evidence_records",sa.Column("issuer_key_id",sa.String(120),nullable=True)); op.add_column("authorization_evidence_records",sa.Column("contract_version",sa.String(40),nullable=True)); op.add_column("authorization_evidence_records",sa.Column("trust_reference",sa.String(200),nullable=True))
def downgrade():
 op.drop_column("authorization_evidence_records","trust_reference"); op.drop_column("authorization_evidence_records","contract_version"); op.drop_column("authorization_evidence_records","issuer_key_id")
