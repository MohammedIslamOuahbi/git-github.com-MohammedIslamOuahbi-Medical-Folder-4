"""Add local revision identity, idempotency, and protected edit attempts.

Revision ID: 20261007_02
Revises: 20261007_01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "20261007_02"
down_revision = "20261007_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind(); inspector = inspect(bind)
    if "local_revisions" not in inspector.get_table_names():
      op.create_table(
        "local_revisions",
        sa.Column("revision_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_revision_uuid", postgresql.UUID(as_uuid=True), sa.ForeignKey("local_revisions.revision_uuid")),
        sa.Column("local_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("operation_uuid", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_uuid", "local_version", name="uq_local_revision_version"),
      )
      op.create_index("ix_local_revisions_entity", "local_revisions", ["entity_type", "entity_uuid"])
    if "local_write_operations" not in inspector.get_table_names():
      op.create_table(
        "local_write_operations",
        sa.Column("operation_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
      )
    if "local_edit_attempts" not in inspector.get_table_names():
      op.create_table(
        "local_edit_attempts",
        sa.Column("operation_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("observed_version", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("attempted_payload", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
      )
    columns = {c["name"] for c in inspect(bind).get_columns("sync_changes")}
    if "revision_uuid" not in columns:
      op.add_column("sync_changes", sa.Column("revision_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    if "operation_uuid" not in columns:
      op.add_column("sync_changes", sa.Column("operation_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    constraints = {c["name"] for c in inspect(bind).get_unique_constraints("sync_changes")}
    if "uq_sync_changes_revision_uuid" not in constraints:
      op.create_unique_constraint("uq_sync_changes_revision_uuid", "sync_changes", ["revision_uuid"])


def downgrade() -> None:
    raise RuntimeError("Revision, event and edit-attempt evidence must be archived before downgrade")
