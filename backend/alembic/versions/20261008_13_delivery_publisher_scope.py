"""Scope deliveries by publication publisher while preserving legacy rows."""
from alembic import op
import sqlalchemy as sa

revision = "20261008_13"
down_revision = "20261008_12"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_constraint("uq_sync_event_delivery_peer", "sync_event_deliveries", type_="unique")
    op.create_unique_constraint(
        "uq_sync_event_delivery_publisher_scope", "sync_event_deliveries",
        ["event_uuid", "peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"],
    )
    op.create_index("ix_sync_event_delivery_publisher_scope", "sync_event_deliveries",
                    ["peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"])

def downgrade():
    op.drop_index("ix_sync_event_delivery_publisher_scope", table_name="sync_event_deliveries")
    op.drop_constraint("uq_sync_event_delivery_publisher_scope", "sync_event_deliveries", type_="unique")
    # Legacy NULL-scoped rows may collide; refuse a destructive downgrade.
    raise RuntimeError("SYNC_DELIVERY_SCOPE_DOWNGRADE_UNSAFE")
