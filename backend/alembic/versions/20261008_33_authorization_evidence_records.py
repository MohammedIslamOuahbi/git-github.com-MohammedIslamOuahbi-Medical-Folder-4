from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261008_33"; down_revision="20261008_32"; branch_labels=None; depends_on=None
def upgrade():
 op.create_table("authorization_evidence_records",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("evidence_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("event_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("operation_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("content_sha256",sa.String(64),nullable=False),sa.Column("subject_user_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("entity_type",sa.String(100),nullable=False),sa.Column("entity_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("clinic_uuid",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("scope",sa.String(200),nullable=False),sa.Column("envelope",postgresql.JSONB,nullable=False),sa.Column("envelope_sha256",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("evidence_uuid",name="uq_authorization_evidence_uuid"))
def downgrade(): op.drop_table("authorization_evidence_records")
