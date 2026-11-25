"""Add durable sync transport inbox, delivery, cursor and attempts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "20261008_01"
down_revision = "20261007_02"
branch_labels = None
depends_on = None


def _uuid(name, nullable=False):
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind(); cols = {c["name"] for c in inspect(bind).get_columns("sync_changes")}
    if "schema_version" not in cols: op.add_column("sync_changes", sa.Column("schema_version", sa.Integer(), nullable=True))
    if "content_sha256" not in cols: op.add_column("sync_changes", sa.Column("content_sha256", sa.String(64), nullable=True))
    if "source_generation_uuid" not in cols: op.add_column("sync_changes", _uuid("source_generation_uuid", nullable=True))
    if "source_sequence" not in cols: op.add_column("sync_changes", sa.Column("source_sequence", sa.BigInteger(), nullable=True))
    # Some installations already contain the transport tables from the initial
    # schema migration; their existence is the authoritative compatibility check.
    if "sync_event_inbox" in inspect(bind).get_table_names():
        return

    op.create_table(
        "sync_event_inbox",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _uuid("event_uuid"), _uuid("source_clinic_uuid"), _uuid("source_device_uuid"),
        _uuid("source_generation_uuid"), sa.Column("source_sequence", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False), _uuid("entity_uuid"),
        _uuid("revision_uuid", nullable=True), _uuid("parent_revision_uuid", nullable=True),
        sa.Column("operation", sa.String(20), nullable=False), sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="received"),
        sa.Column("rejection_code", sa.String(100)), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_uuid", name="uq_sync_event_inbox_event"),
    )
    op.create_index("ix_sync_event_inbox_source", "sync_event_inbox", ["source_clinic_uuid", "source_device_uuid", "source_generation_uuid", "source_sequence"])
    op.create_table(
        "sync_event_deliveries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), _uuid("event_uuid"),
        _uuid("peer_device_uuid"), sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(100)), sa.Column("last_error_message", sa.Text()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False), sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_uuid", "peer_device_uuid", "channel", name="uq_sync_event_delivery_peer"),
    )
    op.create_index("ix_sync_event_deliveries_pending", "sync_event_deliveries", ["peer_device_uuid", "channel", "status", "available_at"])
    op.create_table(
        "sync_transport_cursors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), _uuid("peer_device_uuid"), _uuid("source_device_uuid"),
        _uuid("source_generation_uuid"), sa.Column("channel", sa.String(40), nullable=False), sa.Column("last_source_sequence", sa.BigInteger(), nullable=False, server_default="0"),
        _uuid("last_event_uuid", nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", name="uq_sync_transport_cursor"),
    )
    op.create_table(
        "sync_transport_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), _uuid("event_uuid"), _uuid("peer_device_uuid"),
        sa.Column("channel", sa.String(40), nullable=False), sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False), sa.Column("error_code", sa.String(100)), sa.Column("error_message", sa.Text()),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_transport_attempts_event", "sync_transport_attempts", ["event_uuid", "peer_device_uuid", "channel"])


def downgrade() -> None:
    raise RuntimeError("Refusing to remove durable transport evidence")
