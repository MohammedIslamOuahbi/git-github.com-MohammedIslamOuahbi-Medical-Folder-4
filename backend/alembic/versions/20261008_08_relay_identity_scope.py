"""add explicit relay authorization and publisher identity"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261008_08"
down_revision = "20261008_07"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("sync_relay_authorizations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("carrier_device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin_device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin_generation_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination_device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("carrier_device_uuid", "origin_device_uuid", "origin_generation_uuid", "destination_device_uuid", "channel", name="uq_sync_relay_scope"))
    op.create_index("ix_sync_relay_auth_carrier", "sync_relay_authorizations", ["carrier_device_uuid"])
    op.create_index("ix_sync_relay_auth_origin", "sync_relay_authorizations", ["origin_device_uuid", "origin_generation_uuid"])
    op.add_column("sync_event_publications", sa.Column("publisher_device_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("sync_event_publications", sa.Column("publisher_generation_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_sync_event_publication_publisher", "sync_event_publications", ["publisher_device_uuid", "publisher_generation_uuid", "channel"])
def downgrade():
    op.drop_index("ix_sync_event_publication_publisher", table_name="sync_event_publications")
    op.drop_column("sync_event_publications", "publisher_generation_uuid")
    op.drop_column("sync_event_publications", "publisher_device_uuid")
    op.drop_index("ix_sync_relay_auth_origin", table_name="sync_relay_authorizations")
    op.drop_index("ix_sync_relay_auth_carrier", table_name="sync_relay_authorizations")
    op.drop_table("sync_relay_authorizations")
