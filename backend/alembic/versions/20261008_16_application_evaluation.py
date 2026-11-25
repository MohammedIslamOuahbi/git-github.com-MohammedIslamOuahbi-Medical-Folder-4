"""Stage 5A: durable event evaluation without business application."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_16"; down_revision = "20261008_15"; branch_labels = None; depends_on = None
def upgrade():
    u = postgresql.UUID(as_uuid=True)
    op.create_table("sync_application_decisions", sa.Column("id",sa.BigInteger(),primary_key=True), sa.Column("event_uuid",u,nullable=False), sa.Column("content_sha256",sa.String(64),nullable=False), sa.Column("policy_version",sa.String(40),nullable=False), sa.Column("input_fingerprint",sa.String(64),nullable=False), sa.Column("entity_type",sa.String(100),nullable=False), sa.Column("entity_uuid",u,nullable=False), sa.Column("decision",sa.String(50),nullable=False), sa.Column("reason_code",sa.String(100),nullable=False), sa.Column("evidence_refs",sa.JSON(),nullable=False), sa.Column("evaluated_at",sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint("event_uuid",name="uq_sync_application_decision_event"))
    op.create_index("ix_sync_application_decisions_event_uuid","sync_application_decisions",["event_uuid"]); op.create_index("ix_sync_application_decisions_decision","sync_application_decisions",["decision"])
    op.create_table("sync_application_attempts", sa.Column("id",sa.BigInteger(),primary_key=True), sa.Column("event_uuid",u,nullable=False), sa.Column("content_sha256",sa.String(64),nullable=False), sa.Column("policy_version",sa.String(40),nullable=False), sa.Column("input_fingerprint",sa.String(64),nullable=False), sa.Column("decision",sa.String(50),nullable=False), sa.Column("reason_code",sa.String(100),nullable=False), sa.Column("evidence_refs",sa.JSON(),nullable=False), sa.Column("evaluated_at",sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint("event_uuid","input_fingerprint",name="uq_sync_application_attempt_input"))
    op.create_index("ix_sync_application_attempts_event_uuid","sync_application_attempts",["event_uuid"])
def downgrade(): raise RuntimeError("SYNC_APPLICATION_EVALUATION_DOWNGRADE_UNSAFE")
