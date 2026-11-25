"""Add non-destructive recovery capture register.

Revision ID: 20261007_01
Revises: 20260823_01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261007_01"
down_revision = "20260823_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_sources",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_scope", sa.String(255), nullable=False),
        sa.Column("source_identity", sa.String(255)),
        sa.Column("source_kind", sa.String(50), nullable=False),
        sa.Column("logical_key", sa.String(255), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("byte_length", sa.BigInteger(), nullable=False),
        sa.Column("parent_source_uuid", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_sources.uuid")),
        sa.Column("captured_by_user_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("materialized_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("source_scope", "source_kind", "logical_key", "sha256", name="uq_recovery_source_snapshot"),
    )
    op.create_index("ix_recovery_sources_source_scope", "recovery_sources", ["source_scope"])
    op.create_index("ix_recovery_sources_captured_by_user_uuid", "recovery_sources", ["captured_by_user_uuid"])
    op.create_table(
        "recovery_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_uuid", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_sources.uuid"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=False),
        sa.Column("raw_fragment", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("legacy_id", sa.String(255)),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True)),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.UniqueConstraint("source_uuid", "ordinal", name="uq_recovery_item_position"),
    )
    op.create_index("ix_recovery_items_source_uuid", "recovery_items", ["source_uuid"])
    op.create_table(
        "recovery_identity_candidates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("recovery_items.id"), nullable=False),
        sa.Column("source_scope", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("legacy_id", sa.String(255), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.UniqueConstraint("item_id", name="uq_recovery_identity_item"),
    )


def downgrade() -> None:
    # Recovery evidence must not be silently destroyed by a downgrade.
    raise RuntimeError("Recovery tables contain preserved evidence; manual archival is required before downgrade.")
