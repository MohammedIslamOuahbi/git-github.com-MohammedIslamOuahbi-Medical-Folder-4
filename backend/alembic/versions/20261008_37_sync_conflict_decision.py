"""immutable incoming conflict decision record"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261008_37"
down_revision = "20261008_36"
branch_labels = None
depends_on = None

def upgrade():
    # Some isolated fixtures pre-create metadata tables before Alembic runs.
    # Keep the migration idempotent for those fresh test databases.
    if "sync_conflict_decisions" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "sync_conflict_decisions",
        sa.Column("decision_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("operation_uuid", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("conflict_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incoming_event_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incoming_revision_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_parent_revision_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_revision_uuid", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("local_version", sa.Integer(), nullable=False),
        sa.Column("incoming_version", sa.Integer(), nullable=False),
        sa.Column("local_snapshot", sa.JSON(), nullable=False),
        sa.Column("incoming_snapshot", sa.JSON(), nullable=False),
        sa.Column("local_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("incoming_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("reviewer_user_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("policy_version", sa.String(100)),
        sa.Column("trust_reference", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_conflict_decisions_conflict_uuid", "sync_conflict_decisions", ["conflict_uuid"])

def downgrade():
    op.drop_index("ix_sync_conflict_decisions_conflict_uuid", table_name="sync_conflict_decisions")
    op.drop_table("sync_conflict_decisions")
