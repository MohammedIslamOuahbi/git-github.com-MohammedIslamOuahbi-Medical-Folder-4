"""5A-P1 durable proof wait state, policy snapshot and transport capability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_17"; down_revision = "20261008_16"; branch_labels = None; depends_on = None
def upgrade():
    u = postgresql.UUID(as_uuid=True)
    op.create_table("authorization_policies",
        sa.Column("policy_version", sa.String(40), primary_key=True),
        sa.Column("offline_days", sa.Integer(), nullable=False),
        sa.Column("time_reference", sa.String(40), nullable=False),
        sa.Column("unknown_time_action", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("origin_proof_requests",
        sa.Column("request_uuid", u, primary_key=True),
        sa.Column("operation_uuid", u, nullable=False, unique=True),
        sa.Column("event_uuid", u, nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("revision_uuid", u, nullable=False),
        sa.Column("parent_revision_uuid", u, nullable=True),
        sa.Column("origin_user_uuid", u, nullable=True),
        sa.Column("origin_device_uuid", u, nullable=True),
        sa.Column("clinic_uuid", u, nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("proof_transport_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reason_code", sa.String(100), nullable=True),
        sa.Column("time_state", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_uuid", name="uq_origin_proof_request_event"))
    op.create_index("ix_origin_proof_requests_status", "origin_proof_requests", ["status"])
    op.create_table("proof_transport_capabilities",
        sa.Column("peer_device_uuid", u, primary_key=True),
        sa.Column("max_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
def downgrade():
    raise RuntimeError("PROOF_PENDING_DOWNGRADE_UNSAFE")
